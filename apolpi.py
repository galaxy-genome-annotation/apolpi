import json
import os
import time

from flask import Flask
from flask import jsonify
from flask import request

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

global CACHED_RESULT
global CACHED_TIME
global TIMEOUT
CACHED_RESULT = None
CACHED_TIME = 0
TIMEOUT = int(os.environ.get('TIMEOUT', 30))

app = Flask(__name__)

if 'SQLALCHEMY_DATABASE_URI' in os.environ:
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('SQLALCHEMY_DATABASE_URI')
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://localhost:5432/apollo"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
}

db = SQLAlchemy(app)

QUERY = """
SELECT
    organism.common_name,
    organism.blatdb,
    organism.metadata,
    organism.obsolete,
    organism.directory,
    organism.public_mode,
    organism.valid,
    organism.genome_fasta_index,
    organism.genus,
    organism.species,
    organism.id,
    organism.non_default_translation_table,
    organism.genome_fasta,
    false AS currentorganism,
    sum(
        CASE
        WHEN feature.class
        IN (
                'org.bbop.apollo.RepeatRegion',
                'org.bbop.apollo.Terminator',
                'org.bbop.apollo.TransposableElement',
                'org.bbop.apollo.Gene',
                'org.bbop.apollo.Pseudogene',
                'org.bbop.apollo.PseudogenicRegion',
                'org.bbop.apollo.ProcessedPseudogene',
                'org.bbop.apollo.Deletion',
                'org.bbop.apollo.Insertion',
                'org.bbop.apollo.Substitution',
                'org.bbop.apollo.SNV',
                'org.bbop.apollo.SNP',
                'org.bbop.apollo.MNV',
                'org.bbop.apollo.MNP',
                'org.bbop.apollo.Indel'
            )
        THEN 1
        ELSE 0
        END
    ) AS annotationcount,
    count(distinct sequence.id) AS sequences
FROM
    organism
    LEFT OUTER JOIN sequence ON organism.id = sequence.organism_id
    LEFT OUTER JOIN feature_location ON
            sequence.id = feature_location.sequence_id
    LEFT OUTER JOIN feature ON
            feature.id = feature_location.feature_id
GROUP BY
    organism.common_name,
    organism.blatdb,
    organism.metadata,
    organism.obsolete,
    organism.directory,
    organism.public_mode,
    organism.valid,
    organism.genome_fasta_index,
    organism.genus,
    organism.species,
    organism.id,
    organism.non_default_translation_table,
    organism.genome_fasta
    ;
"""

INSERT = """
INSERT INTO organism
    (id, version, common_name, directory, genome_fasta, genome_fasta_index, genus, species, obsolete, public_mode, valid)
VALUES
    (:id, 2, :commonName, :directory, 'seq/genome.fasta', 'seq/genome.fasta.fai', :genus, :species, false, :publicMode, true);
"""

INSERT_PERMISSIONS = """
INSERT INTO permission
    (id, organism_id, class, user_id, permissions, version)
VALUES
    (:permid, :id, 'org.bbop.apollo.UserOrganismPermission', 31, '["ADMINISTRATE"]', 1);
"""

INSERT_REFSEQ = """
INSERT INTO sequence
    (id, version, sequence_end, length, name, organism_id, sequence_start)
VALUES
    (:refseqid, 0, :length, :length, :name, :id, 0);
"""
#    id    | version | sequence_end | length  |  name   | organism_id | seq_chunk_size | sequence_start
# ---------+---------+--------------+---------+---------+-------------+----------------+----------------
#  5482965 |       0 |       230218 |  230218 | chrI    |     5482963 |                |              0

columns = [
    "commonName", "blatdb", "metadata", "obsolete", "directory",
    "publicMode", "valid", "genomeFastaIndex", "genus", "species", "id",
    "nonDefaultTranslationTable", "genomeFasta", "currentOrganism",
    "annotationCount", "sequences"
]


def _fetch():
    roles = db.session.execute(text(QUERY))
    out = []
    for role in roles:
        out.append(dict(zip(columns, role)))
    return out


def _insert(var):
    # Need to get /data/dnb01/apollo/149296708/seq/refSeqs.json
    refseqjson = os.path.join(var['directory'], 'seq', 'refSeqs.json')
    with open(refseqjson, 'r') as handle:
        refSeqs = json.load(handle)

    # Wrap it all in a connection
    with db.session.begin():
        org_id = list(db.session.execute(text("select max(id) + 2 from organism")))[0][0]
        var['id'] = org_id
        db.session.execute(text(INSERT), var)

        perm_id = list(db.session.execute(text("select max(id) + 2 from permission")))[0][0]
        db.session.execute(text(INSERT_PERMISSIONS), {'permid': perm_id, 'id': org_id})

        max_rowid = list(db.session.execute(text("select max(id) from sequence")))[0][0]
        for i, rec in enumerate(refSeqs):
            refVars = {'refseqid': max_rowid + 1 + i, 'length': rec['length'], 'name': rec['name'], 'id': org_id}
            db.session.execute(text(INSERT_REFSEQ), refVars)

    return True


@app.route("/organism/findAllOrganisms", methods=["GET", "POST"])
def doit():
    global CACHED_TIME
    global CACHED_RESULT
    now = time.time()
    if now - CACHED_TIME > TIMEOUT:
        CACHED_RESULT = _fetch()
        CACHED_TIME = now

    final_list = CACHED_RESULT

    req_json = request.get_json(silent=True)

    # Optional filter by org
    organism = request.args.get('organism', None)
    if organism:
        final_list = [x for x in final_list if str(x['id']) == organism or x['commonName'] == organism]
    elif req_json and 'organism' in req_json:
        organism = req_json['organism']
        if organism:
            final_list = [x for x in final_list if str(x['id']) == organism or x['commonName'] == organism]

    # Optional filter by showPublicOnly
    showPublicOnly = request.args.get('showPublicOnly', None)
    if showPublicOnly:
        final_list = [x for x in final_list if str(x['publicMode']).lower() == str(showPublicOnly).lower()]
    elif req_json and 'showPublicOnly' in req_json:
        showPublicOnly = req_json['showPublicOnly']
        if showPublicOnly:
            final_list = [x for x in final_list if str(x['publicMode']).lower() == str(showPublicOnly).lower()]

    return jsonify(final_list)


@app.route("/organism/addOrganism", methods=["POST"])
def insert():
    req_json = dict(request.json)
    # '{"commonName": "sacCer1 (gx654)",
    #   "directory": "/data/dnb01/apollo/149296708",
    #    "publicMode": false, "genus": "S", "species": "cerevisiae",
    #    "username": "XXXXXXXXX", "password": "XXXXXXXXX"}'
    # -[ RECORD 1 ]-----------------+-----------------------------
    # id                            | 5483083
    # version                       | 2
    # abbreviation                  |
    # blatdb                        |
    # comment                       |
    # common_name                   | sacCer1 (gx654)
    # data_added_via_web_services   |
    # directory                     | /data/dnb01/apollo/149296708
    # genome_fasta                  | seq/genome.fasta
    # genome_fasta_index            | seq/genome.fasta.fai
    # genus                         | S
    # metadata                      | {"creator":"31"}
    # non_default_translation_table |
    # obsolete                      | f
    # public_mode                   | f
    # species                       | cerevisiae
    # valid                         | t
    # official_gene_set_track       |
    print(req_json)
    # This is intensely terrible.
    print(_insert(req_json))
    return doit()

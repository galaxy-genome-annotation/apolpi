import os
import time

from flask import Flask
from flask import jsonify
from flask import request

from flask_sqlalchemy import SQLAlchemy

global CACHED_RESULT
global CACHED_TIME
CACHED_RESULT = None
CACHED_TIME = 0

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

columns = [
    "commonName", "blatdb", "metadata", "obsolete", "directory",
    "publicMode", "valid", "genomeFastaIndex", "genus", "species", "id",
    "nonDefaultTranslationTable", "genomeFasta", "currentOrganism",
    "annotationCount", "sequences"
]


def _fetch():
    roles = db.engine.execute(QUERY)
    out = []
    for role in roles:
        out.append(dict(zip(columns, role)))
    return out


@app.route("/organism/findAllOrganisms", methods=["GET", "POST"])
def doit():
    global CACHED_TIME
    global CACHED_RESULT
    now = time.time()
    if now - CACHED_TIME > 30:
        CACHED_RESULT = _fetch()
        CACHED_TIME = now

    final_list = CACHED_RESULT

    req_json = request.get_json()

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

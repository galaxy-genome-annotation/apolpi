from flask import Flask
from flask import jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import time

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

    return jsonify(CACHED_RESULT)

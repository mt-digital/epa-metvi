import json
import numpy as np
import os
import requests

from datetime import datetime
from flask_security import UserMixin, RoleMixin

from .app import db

DOWNLOAD_BASE_URL = 'https://archive.org/download/'


class Instance(db.EmbeddedDocument):

    text = db.StringField(required=True)
    source_id = db.ObjectIdField(required=True)

    figurative = db.BooleanField(default=False)
    include = db.BooleanField(default=False)

    conceptual_metaphor = db.StringField(default='')
    objects = db.StringField(default='')
    subjects = db.StringField(default='')
    active_passive = db.StringField(default='')
    tense = db.StringField(default='')
    description = db.StringField(default='')
    spoken_by = db.StringField(default='')

    # Has this particular quote been coded already?
    repeat = db.BooleanField(default=False)
    # If so, what is the index of the instance in the facet?
    repeat_index = db.IntField()

    # Is this a re-run (repeat of exact same episode)?
    # If so, it should be excluded, but mark to keep track
    rerun = db.BooleanField(default=False)

    reviewed = db.BooleanField(default=False)

    reference_url = db.URLField()


class Facet(db.Document):

    instances = db.ListField(db.EmbeddedDocumentField(Instance))
    word = db.StringField()
    total_count = db.IntField(default=0)
    number_reviewed = db.IntField(default=0)


class Project(db.Document):

    name = db.StringField(required=True)

    # corpus = db.ReferenceField(IatvCorpus)
    facets = db.ListField(db.ReferenceField(Facet))
    created = db.DateTimeField(default=datetime.now)
    last_modified = db.DateTimeField(default=datetime.now)

    def add_facet_from_search_results(self, facet_label, search_results):

        instances = []
        for res in search_results:

            doc = IatvDocument.from_search_result(res)
            doc.save()
            new_instance = Instance(doc.document_data, doc.id)
            # new_instance.save()
            instances.append(new_instance)

        new_facet = Facet(instances, facet_label, len(instances))
        new_facet.save()

        self.facets.append(new_facet)

        self.save()

    @classmethod
    def from_search_results(cls, faceted_search_results, project_name):
        '''
        Arguments:
            faceted_search_results (dict): e.g.
                {
                    'epa/kill': [instance0, instance1, ...],
                    'epa/strangle': [instance0, ...],
                    'regulations/rob': [...]
                }
        '''
        facets = []

        for facet_label, search_results in faceted_search_results.items():

            instances = []
            for res in search_results:
                doc = IatvDocument.from_search_result(res)
                doc.save()
                new_instance = Instance(doc.document_data, doc.id)
                # new_instance.save()
                instances.append(new_instance)

            new_facet = Facet(instances, facet_label, len(instances))
            new_facet.save()
            facets.append(new_facet)

            instances = []

        return cls(project_name, facets)


class IatvDocument(db.Document):

    document_data = db.StringField(required=True)
    raw_srt = db.StringField()
    iatv_id = db.StringField(required=True)
    iatv_url = db.URLField(required=True)

    network = db.StringField()
    program_name = db.StringField()

    # somewhat redundant in case localtime is missing or other issues
    start_localtime = db.DateTimeField()
    start_time = db.DateTimeField()
    stop_time = db.DateTimeField()
    runtime_seconds = db.FloatField()
    utc_offset = db.StringField()

    datetime_added = db.DateTimeField(default=datetime.now())

    @classmethod
    def from_search_result(cls, search_result):
        '''
        New document from iatv search results. See
        https://archive.org/details/tv?q=epa+kill&time=20151202-20170516&rows=10&output=json
        for an example search result that is parsed
        '''
        sr = search_result

        document_data = sr['snip']
        # eg WHO_20160108_113000_Today_in_Iowa_at_530
        iatv_id = sr['identifier']
        iatv_url = 'https://archive.org/details/' + iatv_id

        id_spl = iatv_id.split('_')

        network = id_spl[0]

        program_name = ' '.join(id_spl[3:])

        # eg 20160108
        air_date_str = id_spl[1]
        # eg 113000; UTC
        air_time_str = id_spl[2]

        start_localtime = datetime(
                int(air_date_str[:4]),
                int(air_date_str[4:6]),
                int(air_date_str[6:]),
                int(air_time_str[:2]),
                int(air_time_str[2:4])
        )

        return cls(document_data, iatv_id=iatv_id, iatv_url=iatv_url,
                   network=network, program_name=program_name,
                   start_localtime=start_localtime)

    def download_video(self, download_dir):

        segments = int(np.ceil(self.runtime_seconds / 60.0))

        for i in range(segments):
            start_time = i * 60
            stop_time = (i + 1) * 60
            download_url = DOWNLOAD_BASE_URL + self.iatv_id + '/' +\
                self.iatv_id + '.mp4?t=' + str(start_time) + '/' +\
                str(stop_time) + '&exact=1&ignore=x.mp4'

            res = requests.get(download_url)

            download_path = os.path.join(
                download_dir, '{}_{}.mp4'.format(self.iatv_id, i))

            with open(download_path, 'wb') as handle:
                handle.write(res.content)


class IatvCorpus(db.Document):

    name = db.StringField()
    documents = db.ListField(db.ReferenceField(IatvDocument))


class Role(db.Document, RoleMixin):
    name = db.StringField(max_length=80, unique=True)
    description = db.StringField(max_length=255)


class User(db.Document, UserMixin):
    email = db.StringField(max_length=255)
    password = db.StringField(max_length=255)
    active = db.BooleanField(default=True)
    confirmed_at = db.DateTimeField()
    roles = db.ListField(db.ReferenceField(Role), default=[])


class Log(db.Document):
    time_posted = db.DateTimeField(default=datetime.now)
    user_email = db.StringField()
    message = db.StringField()

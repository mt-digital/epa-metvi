#! venv/bin/python
'''
export_project_csv.py

Convert `project` collections in MongoDB to a CSV for downstream analysis.

By default includes all the columns as listed in the global DEFAULT_COLUMNS
variable.

Author: Matthew Turner
Date: May 29, 2019
'''
import csv
import pandas as pd

from metacorps.app.models import Project, IatvDocument


IATV_DOCUMENT_COLUMNS = [
    'start_localtime',
    'start_time',
    'stop_time',
    'runtime_seconds',
    'network',
    'program_name',
    'iatv_id',
]

INSTANCE_COLUMNS = [
    'figurative',
    'include',
    'spoken_by',
    'subjects',
    'objects',
    'conceptual_metaphor',
    'active_passive',
    'text',
    'tense',
    'repeat',
    'repeat_index'
]


class ProjectExporter:

    def __init__(self, project_name):
        """
        Initialize a new project exporter
        """

        self.project = Project.objects.get(name=project_name)

        self.keyed_instances = (
            (facet.word, instance)
            for facet in self.project.facets
            for instance in facet.instances
            # if instance.include
        )
        self.column_names =\
            IATV_DOCUMENT_COLUMNS + \
            ['facet_word'] + \
            INSTANCE_COLUMNS

    # def _keyed_instances(self):

    #     return self.keyed_instances

    def export_csv(self, export_path, included_only=True):

        if included_only:
            _keyed_instances = (
                key_inst for key_inst in self.keyed_instances
                if key_inst[1].include
            )
        else:
            _keyed_instances = self.keyed_instances

        with open(export_path, 'w') as f:

            csvwriter = csv.writer(f)

            csvwriter.writerow(self.colunm_names)

            for inst in _keyed_instances:
                csvwriter.writerow(_format_row(inst))

    def export_dataframe(self, included_only=True):

        df = pd.DataFrame(columns=self.column_names)

        if included_only:
            _keyed_instances = (
                key_inst for key_inst in self.keyed_instances
                if key_inst[1].include
            )
        else:
            _keyed_instances = self.keyed_instances

        for idx, inst in enumerate(_keyed_instances):
            df.loc[idx] = _format_row(inst)

        return df


def _lookup_iatv_doc(instance):
    return IatvDocument.objects.get(pk=instance.source_id)


def _format_row(instance):
    iatv_doc = _lookup_iatv_doc(instance[1])
    facet_word = instance[0]
    return [iatv_doc[field] for field in IATV_DOCUMENT_COLUMNS] +\
        [facet_word] + [instance[1][field] for field in INSTANCE_COLUMNS]

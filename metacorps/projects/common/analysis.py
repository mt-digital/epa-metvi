import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd

from collections import OrderedDict, Counter
from copy import deepcopy
from datetime import datetime, timedelta
from urllib.parse import urlparse

from .export_project import ProjectExporter
from metacorps.app.models import IatvCorpus


DEFAULT_FACET_WORDS = [
    'attack',
    'hit',
    'beat',
    'grenade',
    'slap',
    'knock',
    'jugular',
    'smack',
    'strangle',
    'slug',
]


def get_project_data_frame(project_name):
    '''
    Convenience method for creating a newly initialized instance of the
    Analyzer class. Currently the only argument is year since the projects all
    contain a year. In the future we may want to match some other unique
    element of a title, or create some other kind of wrapper to search
    all Project names in the metacorps database.

    Arguments:
        project_name (str): name of project to be exported to an Analyzer
            with DataFrame representation included as an attribute
    '''
    if type(project_name) is int:
        project_name = str('Viomet Sep-Nov ' + str(project_name))

    def is_url(s): return urlparse(project_name).hostname is not None
    if is_url(project_name) or os.path.exists(project_name):
        ret = pd.read_csv(project_name, na_values='',
                          parse_dates=['start_localtime'])
        return ret

    return ProjectExporter(project_name).export_dataframe()


def _select_range_and_pivot_subj_obj(date_range, counts_df, subj_obj):

    rng_sub = counts_df[
        date_range[0] <= counts_df.start_localtime
    ][
        counts_df.start_localtime <= date_range[1]
    ]

    rng_sub_sum = rng_sub.groupby(['network', subj_obj]).agg(sum)

    ret = rng_sub_sum.reset_index().pivot(
        index='network', columns=subj_obj, values='counts'
    )

    return ret


def _count_daily_subj_obj(df, sub_obj):

    subs = df[['start_localtime', 'network', 'subjects', 'objects']]

    subs.subjects = subs.subjects.map(lambda s: s.strip().lower())
    subs.objects = subs.objects.map(lambda s: s.strip().lower())

    try:
        trcl = subs[
            (subs[sub_obj].str.contains('hillary clinton') |
             subs[sub_obj].str.contains('donald trump')) &
            subs[sub_obj].str.contains('/').map(lambda b: not b) &
            subs[sub_obj].str.contains('campaign').map(lambda b: not b)
        ]
    except KeyError:
        raise RuntimeError('sub_obj must be "subjects" or "objects"')

    c = trcl.groupby(['start_localtime', 'network', sub_obj]).size()

    ret_df = c.to_frame()
    ret_df.columns = ['counts']
    ret_df.reset_index(inplace=True)

    # cleanup anything like 'republican nominee'
    ret_df.loc[
        :, sub_obj
    ][

        ret_df[sub_obj].str.contains('donald trump')

    ] = 'donald trump'

    ret_df.loc[
        :, sub_obj
    ][

        ret_df[sub_obj].str.contains('hillary clinton')

    ] = 'hillary clinton'

    return ret_df


def _count_by_start_localtime(df,
                              column_list=['program_name',
                                           'network',
                                           'facet_word']):
    '''
    Count the number of instances grouped by column_list. Adds a 'counts'
    column.

    Arguments:
        df (pandas.DataFrame): Analyzer.df attribute from Analyzer class
        column_list (list): list of columns on which to groupby then count

    Returns:
        (pandas.DataFrame) counts per start_localtime of tuples with types
            given in column_list
    '''
    all_cols = ['start_localtime'] + column_list

    subs = df[all_cols]

    c = subs.groupby(all_cols).size()

    ret_df = c.to_frame()
    ret_df.columns = ['counts']
    ret_df.reset_index(inplace=True)

    return ret_df


def shows_per_date(date_index, iatv_corpus, by_network=False):
    '''
    Arguments:
        date_index (pandas.DatetimeIndex): Full index of dates covered by
            data
        iatv_corpus (app.models.IatvCorpus): Obtained, e.g., using
            `iatv_corpus = IatvCorpus.objects.get(name='Viomet Sep-Nov 2016')`
        by_network (bool): whether or not to do a faceted daily count
            by network

    Returns:
        (pandas.Series) if by_network is False, (pandas.DataFrame)
            if by_network is true.
    '''
    if type(iatv_corpus) is str:
        iatv_corpus = IatvCorpus.objects(name=iatv_corpus)[0]

    docs = iatv_corpus.documents

    n_dates = len(date_index)

    if not by_network:

        # get all date/show name tuples & remove show re-runs from same date
        prog_dates = set(
            [
                (d.program_name, d.start_localtime.date())
                for d in docs
            ]
        )

        # count total number of shows on each date
        # note we count the second entry of the tuples, which is just the
        # date, excluding program name
        shows_per_date = Counter(el[1] for el in prog_dates)

        spd_series = pd.Series(
            index=date_index,
            data={'counts': np.zeros(n_dates)}
        ).sort_index()

        for date in shows_per_date:
            spd_series.loc[date] = shows_per_date[date]

        return spd_series

    else:
        # get all date/network/show name tuples
        # & remove show re-runs from same date
        prog_dates = set(
            [
                (d.program_name, d.network, d.start_localtime.date())
                for d in docs
            ]
        )

        # count total number of shows on each date for each network
        # note we count the second entry of the tuples, which is just the
        # date, excluding program name
        shows_per_network_per_date = Counter(el[1:] for el in prog_dates)

        n_dates = len(date_index)
        spd_frame = pd.DataFrame(
            index=date_index,
            data={
                'MSNBCW': np.zeros(n_dates),
                'CNNW': np.zeros(n_dates),
                'FOXNEWSW': np.zeros(n_dates)
            }
        )

        for tup in shows_per_network_per_date:
            spd_frame.loc[tup[1]][tup[0]] = shows_per_network_per_date[tup]

        return spd_frame


def daily_metaphor_counts(df, date_index, by=None):
    '''
    Given an Analyzer.df, creates a pivot table with date_index as index. Will
    group by the column names given in by. First deals with hourly data in
    order to build a common index with hourly data, which is the data's
    original format.

    Arguments:
        df (pandas.DataFrame)
        by (list(str))
        date_index (pandas.core.indexes.datetimes.DatetimeIndex): e.g.
            `pd.date_range('2016-09-01', '2016-11-30', freq='D')`
    '''
    # get initial counts by localtime
    if by is None:
        by = []

    counts = _count_by_start_localtime(df, column_list=by)

    groupby_spec = [counts.start_localtime.dt.date, *counts[by]]

    counts_gb = counts.groupby(groupby_spec).sum().reset_index()

    ret = pd.pivot_table(counts_gb, index='start_localtime', values='counts',
                         columns=by, aggfunc='sum').fillna(0)

    return ret


def daily_frequency(df, date_index, iatv_corpus, by=None):

    if by is not None and 'network' in by:
        spd = shows_per_date(date_index, iatv_corpus, by_network=True)
        daily = daily_metaphor_counts(df, date_index, by=by)
        ret = daily.div(spd, axis='rows')

    elif by is None:
        spd = shows_per_date(date_index, iatv_corpus)
        daily = daily_metaphor_counts(df, date_index, by=by)
        ret = daily.div(spd, axis='rows')
        ret.columns = ['freq']

    else:
        spd = shows_per_date(date_index, iatv_corpus)
        daily = daily_metaphor_counts(df, date_index, by=by)
        ret = daily.div(spd, axis='rows')

    return ret


class SubjectObjectData:
    '''
    Container for timeseries of instances of a specified subject, object, or
    subject-object pair. For example, we may look for all instances where
    Donald Trump is the subject of metaphorical violence, irrespective of the
    object. We also may want to see where he is the object, no matter who
    is the subject. Or, we may want to search for pairs, say, all instances
    where Hillary Clinton is the subject of metaphorical violence and
    Donald Trump is the object of metaphorical violence, or vice-versa.

    from_analyzer_df is currently the most likely constructor to be used
    '''

    def __init__(self, data_frame, subj, obj, partition_infos=None):
        self.data_frame = data_frame
        self.subject = subj
        self.object = obj
        self.partition_infos = partition_infos
        self.partition_data_frame = None

    @classmethod
    def from_analyzer_df(cls, analyzer_df, subj=None, obj=None,
                         subj_contains=True, obj_contains=True,
                         date_range=None):
        '''
        Given an Analyzer instance's DataFrame, calculate the frequency of
        metaphorical violence with a given subject, object,
        or a subject-object pair.

        Returns:
            (SubjectObjectData) an initialized class. The data_frame attribute
            will be filled with by-network counts of the specified subj/obj
            configuration.
        '''

        if date_range is None:
            pd.date_range('2016-09-01', '2016-11-30', freq='D')

        pre = analyzer_df.fillna('')

        def _match_checker(df, subj, obj, subj_contains, obj_contains):
            '''
            Returns list of booleans for selecting subject and object matches
            '''

            if subj is None and obj is None:
                raise RuntimeError('subj and obj cannot both be None')

            if subj is not None:
                if subj_contains:
                    retSubj = list(df.subjects.str.contains(subj))
                else:
                    retSubj = list(df.subjects == subj)

                if obj is None:
                    ret = retSubj

            # TODO could probably combine these, but now not clear how
            if obj is not None:
                if obj_contains:
                    retObj = list(df.objects.str.contains(obj))
                else:
                    retObj = list(df.objects == obj)

                if subj is None:
                    ret = retObj
                else:
                    ret = [rs and ro for rs, ro in zip(retSubj, retObj)]

            return ret

        chooser = _match_checker(pre, subj, obj, subj_contains, obj_contains)

        pre = pre[
            chooser
        ]

        # then do counts or frequencies as normal, since you have just
        # subset the relevant rows.
        counts_df = pd.DataFrame(
            index=date_range, data=0.0,
            columns=pd.Index(['MSNBCW', 'CNNW', 'FOXNEWSW'], name='network')
        )

        # there might be columns missing, so we have to insert into above zeros
        to_insert_df = daily_metaphor_counts(pre, date_range, by=['network'])

        for network in ['MSNBCW', 'CNNW', 'FOXNEWSW']:
            if network in to_insert_df.columns:
                for row in to_insert_df.itertuples():
                    counts_df.loc[row.Index][network] = \
                            row.__getattribute__(network)

        return cls(counts_df, subj, obj)

    def partition(self, partition_infos):
        pass


def facet_word_count(analyzer_df, facet_word_index, by_network=True):
    '''
    Count the number of times each facet word has been used. If by_network is
    True, compute the usage of each word by network.

    Arguments:
        analyzer_df (pandas.DataFrame): dataframe of the IatvCorpus annotations
        by_network (bool): group each partition's word counts by network?

    Returns:
        (pandas.DataFrame) or (pandas.Series) of counts depending on by_network
    '''
    if by_network:
        return analyzer_df.groupby(
                ['network', 'facet_word']
            ).size().unstack(level=0)[
                ['MSNBCW', 'CNNW', 'FOXNEWSW']
            ].loc[facet_word_index].fillna(0.0)
    else:
        return analyzer_df.groupby(
                ['facet_word']
            ).size().loc[facet_word_index].fillna(0.0)

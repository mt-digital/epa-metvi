import json

from flask import Flask, render_template, redirect, url_for, jsonify, request
from flask_mongoengine import MongoEngine
from flask_security import (
    MongoEngineUserDatastore, Security, login_required, logout_user,
    current_user
)
from flask_wtf import FlaskForm
from wtforms import validators
from wtforms import TextField, TextAreaField, BooleanField, RadioField

app = Flask(__name__)

app.config.from_envvar('CONFIG_FILE')
app.config['SECURITY_PASSWORD_SALT'] = '/2aX16zPnnIgfMwkOjGX4S'

db = MongoEngine(app)

from . import models



def previously_used_cm():
    facets = [facet
              for project in models.Project.objects
              for facet in project.facets]

    instances = [instance for facet in facets for instance in facet.instances]

    conceptual_metaphors = list(set(
        i['conceptual_metaphor'].lower().strip() for i in instances
        if i['conceptual_metaphor'] != ''
    ))

    return conceptual_metaphors


PREVIOUSLY_USED_CM = previously_used_cm()

user_datastore = MongoEngineUserDatastore(db, models.User, models.Role)
security = Security(app, user_datastore)

DOWNLOAD_BASE_URL = 'https://archive.org/download/'


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')


@app.route('/', methods=['GET', 'POST'])
@login_required
def hello():
    projects = models.Project.objects
    log = list(models.Log.objects)[-10:]
    log.reverse()

    form = LogForm()

    if form.validate_on_submit():
        new_log = models.Log()
        new_log.user_email = current_user.email
        new_log.message = form.message.data

        new_log.save()

        return redirect('/')

    return render_template('index.html', projects=projects, log=log, form=form)


class LogForm(FlaskForm):
    message = TextAreaField(u'Log Entry:', [validators.DataRequired()])


@app.route('/projects/<project_id>')
@login_required
def project(project_id):

    project = models.Project.objects.get(pk=project_id)
    facets = project.facets

    return render_template('project.html',
                           facets=facets,
                           project=project)


@app.route('/projects/<project_id>/facets/<facet_word>')
@login_required
def facet(project_id, facet_word):

    project = models.Project.objects.get(pk=project_id)
    facet = [f for f in project.facets if facet_word == f['word']][0]
    iatv_documents = [
        models.IatvDocument.objects.get(pk=instance.source_id)
        for instance in facet.instances
    ]

    return render_template('facet.html',
                           project=project, facet=facet,
                           iatv_documents=iatv_documents)


@app.route('/api/projects/<project_id>/facets/<facet_word>/instances/<int:instance_idx>',
           methods=['GET', 'POST'])
@login_required
def api_update_instance(project_id, facet_word, instance_idx):

    project = models.Project.objects.get(pk=project_id)
    facet = [f for f in project.facets if facet_word == f['word']][0]

    instance = facet.instances[instance_idx]

    if request.method == 'POST':

        data = request.form

        try:
            instance.figurative = data['figurative'] == 'True'
            instance.include = data['include'] == 'True'
            instance.spoken_by = data['spoken_by']
            instance.conceptual_metaphor = data['conceptual_metaphor']
            instance.objects = data['objects']
            instance.subjects = data['subjects']
            instance.description = data['description']
            instance.tense = data['tense']
            instance.active_passive = data['active_passive']
            instance.repeat = data['repeat'] == 'True'
            ri = data['repeat_index']
            if ri != '' and ri is not None:
                instance.repeat_index = int(ri)
            instance.rerun = data['rerun'] == 'True'
            instance.save()

        except Exception as e:
            print(e)

    return jsonify(json.loads(instance.to_json()))


@app.route('/projects/<project_id>/facets/<facet_word>/instances/<int:instance_idx>', methods=['GET', 'POST'])
@login_required
def edit_instance(project_id, facet_word, instance_idx):

    project = models.Project.objects.get(pk=project_id)
    facet = [f for f in project.facets if facet_word == f['word']][0]

    instance = facet.instances[instance_idx]
    total_instances = len(facet.instances)

    source_doc = models.IatvDocument.objects.get(pk=instance.source_id)

    form = EditInstanceForm(
        figurative=instance['figurative'],
        include=instance['include'],
        spoken_by=instance['spoken_by'],
        conceptual_metaphor=instance['conceptual_metaphor'],
        objects=instance['objects'],
        subjects=instance['subjects'],
        tense=instance['tense'],
        active_passive=instance['active_passive'],
        description=instance['description']
    )

    if form.validate_on_submit():

        cm = form.conceptual_metaphor.data.lower().strip()
        fig = form.figurative.data
        inc = form.include.data
        sp_by = form.spoken_by.data
        obj = form.objects.data
        subj = form.subjects.data

        ap = form.active_passive.data
        desc = form.description.data

        instance['spoken_by'] = sp_by
        instance['conceptual_metaphor'] = cm
        instance['figurative'] = fig
        instance['include'] = inc
        instance['objects'] = obj
        instance['subjects'] = subj

        try:
            t = form.tense.data
            instance['tense'] = t
        except:
            instance['tense'] = ''

        instance['active_passive'] = ap
        instance['description'] = desc

        instance.save()

        if cm not in PREVIOUSLY_USED_CM:
            PREVIOUSLY_USED_CM.append(cm)

        next_url = url_for(
               'edit_instance', project_id=project_id, facet_word=facet_word,
                instance_idx=instance_idx+1
            )

        return redirect(next_url)

    return render_template('edit_instance.html', form=form,
                           project=project, facet=facet,
                           instance_idx=instance_idx, instance=instance,
                           source_doc=source_doc,
                           total_instances=total_instances)


@app.route('/all_conceptual_metaphors', methods=['GET'])
def get_conceptual_metaphors():
    '''
    Get conceptual metaphors used across all projects. Can set up separate
    route later for more refined requests if necessary.
    '''

    return jsonify({'conceptual_metaphors': PREVIOUSLY_USED_CM})


class EditInstanceForm(FlaskForm):

    figurative = BooleanField()
    include = BooleanField()
    conceptual_metaphor = TextField(u'Conceptual metaphor')
    objects = TextField(u'Object(s)')
    subjects = TextField(u'Subject(s)')
    active_passive = TextField(u'Active or passive')
    spoken_by = TextField(u'Spoken by')
    tense = RadioField(
        u'Tense',
        choices=[('past', 'Past'),
                 ('present', 'Present'),
                 ('future', 'Future')],
        validators=None)
    description = TextAreaField(u'Description')

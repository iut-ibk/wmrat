from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils.timezone import make_aware
from django.conf import settings
from django.core.paginator import Paginator

from .forms import EPANETUploadFileForm

from django_rq import job
import django_rq
from rq import cancel_job

import datetime as dt
import json
import uuid
import os
import subprocess as sp
from pathlib import Path
import shutil
import time
import signal

from hub.models import Scenario, WMNetwork

@login_required
def archive(request):
    scenarios = Scenario.objects.filter()
    scenarios = scenarios.order_by('-submitted')

    paginator = Paginator(scenarios, settings.ROWS_PER_PAGE)

    page_nr = request.GET.get('p')
    page_obj = paginator.get_page(page_nr)

    # maybe not needed ... (useful for search) ...
    query_list = []
    for key in request.GET.keys():
        if key == 'p':
            continue

        val = request.GET.get(key)
        if val:
            query_list.append(key + '=' + val)

    query_str = '&'.join(query_list)

    context = {
        'page_title': "WMRAT: Water Management Resilience Analysis Toolkit",
        'page_obj': page_obj,
        'query_str': query_str,
    }

    return render(request, 'archive.html', context)

@login_required
def epanet_archive(request):
    networks = WMNetwork.objects.filter()
    networks = networks.order_by('-uploaded_at')

    paginator = Paginator(networks, settings.ROWS_PER_PAGE)

    page_nr = request.GET.get('p')
    page_obj = paginator.get_page(page_nr)

    # maybe not needed ... (useful for search) ...
    query_list = []
    for key in request.GET.keys():
        if key == 'p':
            continue

        val = request.GET.get(key)
        if val:
            query_list.append(key + '=' + val)

    query_str = '&'.join(query_list)

    context = {
        'page_title': 'WMRAT: Water Management Networks Archive',
        'page_obj': page_obj,
        'query_str': query_str,
    }

    #XXX todo
    return render(request, 'epanet_archive.html', context)

@login_required
def visualize_result(request, scenario_id):
    scenario = get_object_or_404(Scenario, id=scenario_id)

    scenario_path = settings.WMRAT_SCENARIO_DIR / str(scenario.id)

    #TODO: hacky ... (we do that 2x)

    new_results_name = f'{scenario.id}_{scenario.name}'.replace(' ', '_')
    svg_path = scenario_path / new_results_name / 'pipe_criticality_viz.svg'

    #XXX: extremely hacky:
    str_buf = []
    with open(svg_path) as f:
        for n, line in enumerate(f):
            if n < 3:
                continue
            
            str_buf.append(line)
    
    str_buf = ''.join(str_buf)

    context = {
        'page_title': 'Result', #TODO: better name
        'scenario': scenario,
        'svg_data': str_buf,
    }
    return render(request, 'visualize_result.html', context)

@login_required
def import_network(request):
    if request.method == 'POST': #NOTE [... and request.FILES['epanet_file']:
        form = EPANETUploadFileForm(request.POST, request.FILES)
        if form.is_valid(): #XXX: when exactlcy not valid?
            epanet_file = request.FILES['epanet_file']

            #TODO: parse it (so we try to don't import incorrect files)
            epanet_model_name = request.POST.get('epanet_model_name') #TODO: do we need it the 'forms.py'?

            network = WMNetwork(
                name=epanet_model_name,
                #epanet_data='empty',
                opt_param={},
            )

            network.save()

            epanet_model_dir = settings.WMRAT_NETWORK_DIR / str(network.id)

            if not os.path.exists(epanet_model_dir):
                os.makedirs(epanet_model_dir)

            epanet_model_path = epanet_model_dir / 'network.inp'
            with open(epanet_model_path, 'wb+') as f:
                for chunk in epanet_file.chunks():
                    f.write(chunk)

            #TODO: for debugging ...
            print('EPANET input file written')
            return HttpResponseRedirect(reverse('epanet_archive', args=()))

        #TODO: ... and here?

    else:
        form = EPANETUploadFileForm()

    context = {
        'page_title': "WMRat: Import Water Network",
        'form': form
    }

    return render(request, 'import.html', context)

@login_required
def new(request):
    if request.method == 'POST':
        arg_dict = request.POST.dict()
        arg_dict.pop('csrfmiddlewaretoken')

        #print(arg_dict)
        network_id = int(arg_dict['network_id'])

        print(network_id)

        #NOTE: we do not check input (rely on JS validation, but should do that here too)
        scenario = Scenario(
            name=arg_dict['scenario_name'],
            proc_status=Scenario.STATUS_QUEUED,
            submitted=make_aware(dt.datetime.now()),
            user=request.user,
            duration_s=-1,
            info_msg='Scenario created',
            input_json=arg_dict,
            wm_network=WMNetwork.objects.get(id=network_id),
        )

        scenario.save()

        queue = django_rq.get_queue('crunch')
        job = queue.enqueue(do_run_analysis, scenario)

        scenario.job_id = job.id
        scenario.save()

        return HttpResponseRedirect(reverse('archive', args=()))

    networks = WMNetwork.objects.filter()
    networks = networks.order_by('-uploaded_at')

    context = {
        'page_title': 'WMRat: New Scenario',
        'networks': networks,
    }

    return render(request, 'new.html', context)

@job
def do_run_analysis(scenario):
    then = dt.datetime.now()

    scenario.proc_status = Scenario.STATUS_PROCESSING
    scenario.info_msg = f'Running scenario "{scenario.name}" ...'
    scenario.save()

    scenario_path = settings.WMRAT_SCENARIO_DIR / str(scenario.id)
    result_dir = scenario_path / 'results'
    if not os.path.exists(scenario_path):
        os.makedirs(scenario_path)
        os.makedirs(result_dir)

    # EPANET file
    epanet_file_path = settings.WMRAT_NETWORK_DIR / str(scenario.wm_network.id) / 'network.inp'
    #print(epanet_file_path)

    # param JSON
    input_json_path = scenario_path / 'param.json'
    with open(input_json_path, 'w') as f:
        f.write(json.dumps(scenario.input_json))

    script = settings.PROC_PATH
    args = ['python3', script, epanet_file_path, input_json_path, result_dir] #XXX: add json file

    p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.PIPE)
    scenario.proc_pid = p.pid
    scenario.save()

    out, err = p.communicate()

    # to get potential status change (user cancelled *running* job)
    scenario.refresh_from_db()

    elapsed_time_s = (dt.datetime.now() - then).total_seconds()
    scenario.duration_s = elapsed_time_s

    if p.returncode != 0:
        if scenario.proc_status == Scenario.STATUS_CANCELLING:
            scenario.proc_status = Scenario.STATUS_CANCELLED
            scenario.info_msg = f'Cancelled'
        else:
            scenario.proc_status = Scenario.STATUS_FAILED
            if elapsed_time_s > settings.MAX_PROCESSING_TIME:
                scenario.info_msg = f'Maximum execution time ({settings.MAX_PROCESSING_TIME}s) exceeded'
            else:
                scenario.info_msg = f'Analysis failed [{p.returncode}]: {err.decode()}'
    else:
        scenario.proc_status = Scenario.STATUS_SUCCESS
        scenario.info_msg = f'Finished'

    zip_scenario(scenario)

    #TODO: maybe delete potential temporary files

    scenario.save()
    return True #NOTE: yes?

def zip_scenario(scenario):
    scenario_path = settings.WMRAT_SCENARIO_DIR / str(scenario.id)

    new_results_name = f'{scenario.id}_{scenario.name}'.replace(' ', '_')
    zip_name = f'{new_results_name}.zip'

    os.rename(scenario_path / 'results', scenario_path / new_results_name)

    p = sp.Popen(['zip', '-r', zip_name, new_results_name], stdout=sp.PIPE, stderr=sp.PIPE, cwd=scenario_path)
    out, err = p.communicate()

@login_required
def download(request, scenario_id):
    scenario = get_object_or_404(Scenario, id=scenario_id)

    scenario_path = settings.WMRAT_SCENARIO_DIR / str(scenario.id)

    name = f'{scenario.id}_{scenario.name}.zip'.replace(' ', '_')
    path = scenario_path / name

    content_type = 'application/zip'

    resp = HttpResponse(open(path, 'rb'), content_type=content_type)
    resp['Content-Disposition'] = 'attachment; filename={}'.format(name)
    return resp

@login_required
def delete(request, scenario_id):
    scnenario = get_object_or_404(Scenario, id=scenario_id)

    if scnenario.user.id != request.user.id:
        return HttpResponseForbidden('Forbidden')

    scnenario.delete()

    queue = django_rq.get_queue('delete')
    queue.enqueue(do_delete, scenario_id)

    return HttpResponseRedirect(reverse('archive', args=()))

@job
def do_delete(scenario_id):
    scenario_path = settings.WMRAT_SCENARIO_DIR / str(scenario_id)

    # should exist, but check anyway
    if os.path.exists(scenario_path):
        shutil.rmtree(scenario_path)

@login_required
def cancel(request, scenario_id):
    scenario = get_object_or_404(Scenario, id=scenario_id)

    print(scenario.proc_pid)
    if scenario.user.id != request.user.id:
        return HttpResponseForbidden('Forbidden')

    # queued, but not run
    if scenario.proc_status == Scenario.STATUS_QUEUED:
        cancel_job(scenario.job_id, connection=django_rq.get_connection('crunch'))
        scenario.proc_status = Scenario.STATUS_CANCELLED
        scenario.info_msg = 'Cancelled'

    # running
    elif scenario.proc_status == Scenario.STATUS_PROCESSING:
        queue = django_rq.get_queue('cancel')
        queue.enqueue(do_cancel, scenario)

        scenario.proc_status = Scenario.STATUS_CANCELLING
        scenario.info_msg = 'Cancelling ...'

    scenario.save()
    return HttpResponseRedirect(reverse('archive', args=()))

@job
def do_cancel(scenario):
    wait_time = 2 #XXX: can do that again?
    try:
        # kill process here (TODO: what if we don't find the pid?)
        # NOTE: we might not have the pid ... ?
        os.kill(scenario.proc_pid, signal.SIGKILL)
    except Exception as e:
        #NOTE: what to do here?
        pass


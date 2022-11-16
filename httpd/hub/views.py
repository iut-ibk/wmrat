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
from pyproj import Transformer
import numpy as np #XXX: import sauhaufen, tests, schoenes html, schoenes dev setup (podman), schoene CI, schoener test, notify, aber dann ...
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
def explore(request, network_id):
    network = get_object_or_404(WMNetwork, id=network_id)

    network_path = settings.WMRAT_SCENARIO_DIR
    network_path = settings.WMRAT_NETWORK_DIR / str(network.id)

    context = {
    }

    then = dt.datetime.now()

    epanet_network_path = os.path.join(settings.WMRAT_NETWORK_DIR, str(network.id), 'network.inp')

    with open(epanet_network_path) as f:
        lines = []
        for line in f:
            lines.append(line)

    json_graph, diameters = epanet2geojson(lines)
    elapsed_time_s = (dt.datetime.now() - then).total_seconds()

    print(f'parsing and making geojson took: {elapsed_time_s}')

    color_ramp = make_red_green_color_ramp_dict(diameters)

    context = {
        'page_title': 'WMRat: Explore Network',
        'graph': json_graph,
        'color_ramp': color_ramp,
        'network': network,
    }

    return render(request, 'explore_network.html', context)

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

def epanet2geojson(inp_lines):
    pipes = {}
    coords = {}

    diameters = set()

    # parse it ...
    in_pipe_section = False
    in_coordinates_section = False
    for line in inp_lines:
        line = line.split(';')[0].strip()
        if not line:
            continue

        if line.startswith('[PIPES]'):
            in_pipe_section = True
            continue

        if line.startswith('[COORDINATES]'):
            in_coordinates_section = True
            continue

        if in_pipe_section:
            parts = line.split()
            if len(parts) == 8:
                pipe_params = parts
                key = parts[0]
                node1, node2 = parts[1:3]

                diameter = int(parts[4])
                diameters.add(diameter)

                pipes[key] = {
                    'node0': node1,
                    'node1': node2,
                    'diameter': diameter,
                }
            else:
                in_pipe_section = False

        if in_coordinates_section:
            parts = line.split()
            if len(parts) == 3:
                key, c0, c1 = parts[:3]
                coords[key] = {
                    'c0': c0,
                    'c1': c1,
                }
            else:
                in_coordinates_section = False

    # ... make GeoJSON
    geojson = {
        'type': 'FeatureCollection',
        'name': 'pipe_diameters',
        'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:EPSG::3857'}},
        'features': [],
    }

    trans_3857_to_4326 = Transformer.from_crs('EPSG:3857', 'EPSG:4326')

    features = []
    for value_dict in pipes.values():
        n0_c0, n0_c1 = list(map(float, coords[value_dict['node0']].values()))
        n1_c0, n1_c1 = list(map(float, coords[value_dict['node1']].values()))

        #XXX: why are they reversed (e.g. also in dynavibe; bug in dynavibe?)
        n0_c1, n0_c0 = trans_3857_to_4326.transform(n0_c0, n0_c1)
        n1_c1, n1_c0 = trans_3857_to_4326.transform(n1_c0, n1_c1)

        diameter = value_dict['diameter']
        feature = {
            'type': 'Feature',
            'properties': {
                'd': float(diameter),
            },
            'geometry': {
                'type': 'LineString',
                'coordinates': [[n0_c0, n0_c1], [n1_c0, n1_c1]],
            }
        }

        features.append(feature)
    geojson['features'] = features
    return geojson, list(sorted(diameters))

def make_red_green_color_ramp_dict(diameters):
    n = len(diameters)

    green_vals = np.linspace(0, 255, n, dtype=np.uint8)

    colors = []
    for i, green in enumerate(green_vals):
        color = green_vals[n - i - 1], green, 0
        hex_color = '#%02x%02x%02x' % color

        colors.append(hex_color)

    #NOTE: most common (smalltest) diameters gets black color
    colors[-1] = '#000000'

    return dict(zip(diameters, reversed(colors)))


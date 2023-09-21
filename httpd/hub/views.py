from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseServerError
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
import glob
import os
import subprocess as sp
from pathlib import Path
import shutil
import time
import sys
import numpy as np
import signal

from hub.models import Analysis, WMNetwork

import epanet_util as enu

@login_required
def archive(request):
    analyses = Analysis.objects.filter()
    analyses = analyses.order_by('-submitted')

    paginator = Paginator(analyses, settings.ROWS_PER_PAGE)

    page_nr = request.GET.get('p')
    page_obj = paginator.get_page(page_nr)

    #NOTE: maybe not needed ... (useful for search) ...
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
def visualize_result(request, analysis_id):
    analysis = get_object_or_404(Analysis, id=analysis_id)

    analysis_name = analysis.name
    analysis_type = analysis.analysis_type

    network = analysis.wm_network

    network_path = settings.WMRAT_NETWORK_DIR / str(network.id)

    with open(network_path / 'gis' / 'links.geojson') as f:
        geojson_links = json.load(f)

    with open(network_path / 'gis' / 'nodes.geojson') as f:
        geojson_nodes = json.load(f)

    #TODO: hacky ... (we do that 2x)
    analysis_path = settings.WMRAT_ANALYSIS_DIR / str(analysis.id)
    new_results_name = f'{analysis.id}_{analysis.name}'.replace(' ', '_')

    success, val = get_analyses_info_dict_with_defaults()
    if not success:
        err_str = val
        return HttpResponseServerError(err_str)

    analyses_info_all = val

    #print(analyses_info_all)

    analyses_info = analyses_info_all[analysis.analysis_type]

    file_name = analyses_info['output']['file_name']
    property_name = analyses_info['output']['property_name']

    pretty_analysis_type = analyses_info['pretty']

    pretty_output_name = analyses_info['output']['pretty']

    json_path = analysis_path / new_results_name / file_name

    #XXX: currently we only support to append to links
    with open(json_path) as f:
        link_infos = json.load(f)

    #print(links)

    for link in geojson_links['features']:
        link_name = link['properties']['id']
        if link_name in link_infos:
            val = link_infos[link_name]
        else:
            #XXX: hacky
            val = [] if analysis.analysis_type == 'single_pipe_failure_epanet' else 0 #XXX: not really correct, but fow now ...

        link['properties'][property_name] = val

    print('len', len(link_infos))

    plot_data = []
    for k, v in link_infos.items():
        data_point = {
            'label': k,
            #XXX
            'value': len(v) if analysis.analysis_type == 'single_pipe_failure_epanet' else v,
        }
        plot_data.append(data_point)

    plot_data = sorted(plot_data, key=lambda entry: entry['value'], reverse=True)[:25]

    #print(plot_data)

    context = {
        'default_color_ramp': ('#ff0000', '#00ff00'),
        'page_title': 'Result', #TODO: better name
        'links_geojson': geojson_links,
        'nodes_geojson': geojson_nodes,
        'analysis': analysis,
        'pretty_analysis_type': pretty_analysis_type,
        'network': network, #XXX?
        'plot_data': plot_data,
        'pretty_output_name': pretty_output_name,
    }

    return render(request, 'visualize_result.html', context)

def get_analyses_info_dict_with_defaults():
    # get all supported analyses
    spec_jsons = list(glob.glob(str(settings.WMRAT_ANALYSIS_TOOLKIT_DIR) + '/*/spec.json'))
    if len(spec_jsons) == 0:
        return HttpResponseServerError('no supported analyses found')

    print(f'{len(spec_jsons)} analyses found', file=sys.stderr)

    # make information dictionary about these
    analyses_info_dict = {}
    for spec_json_path in spec_jsons:
        key = os.path.basename(Path(spec_json_path).parent)

        try:
            with open(spec_json_path) as f:
                analysis_info = json.load(f)
        except Exception as e:
            return False, f'{spec_json_path}: parse error'

        ex_path = Path(spec_json_path).parent / 'ex1.json'
        try:
            with open(ex_path) as f:
                ex_info = json.load(f)
        except Exception as e:
            return False, f'{ex_path}: parse error'

        #NOTE: guard against typos, etc.:
        if set(analysis_info['params'].keys()) != set(ex_info.keys()):
            return False, f'{key}: parameter mismatch'

        for key_name, key_val in ex_info.items():
            if analysis_info['params'][key_name]['type'] == 'ARRAY':
                analysis_info['params'][key_name]['default'] = ','.join(key_val)
            else:
                analysis_info['params'][key_name]['default'] = key_val

        analyses_info_dict[key] = analysis_info

    #print(analyses_info_dict)
    return True, analyses_info_dict

@login_required
def import_network(request):
    if request.method == 'POST': #NOTE [... and request.FILES['epanet_file']:
        form = EPANETUploadFileForm(request.POST, request.FILES)
        if form.is_valid(): #XXX: when exactlcy not valid?
            epanet_file = request.FILES['epanet_file']

            #TODO: parse it (so we try to don't import incorrect files)
            epanet_model_name = request.POST.get('epanet_model_name') #TODO: do we need it the 'forms.py'?

            #TODO: maybe add/save later to DB (first errors and look for errors)
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

            success, val = enu.epanet_inp_read(epanet_model_path)
            if not success:
                return HttpResponseBadRequest(f'unable to parse EPANET input file')

            epanet_dict = val

            #TODO: run it here => 1) have input sanity check 2) could provide results in explore

            #XXX: do not hard-code this ... when importing demand it from the user?
            epanet_epsg_code = 31254

            success, val = enu.epanet_to_graph(epanet_dict)
            if not success:
                return HttpResponseServerError(f'unable to build graph from EPANET input')

            nodes, links = val
            success, val = enu.graph_to_geojsons(nodes, links, epanet_epsg_code)
            if not success:
                return HttpResponseServerError(f'unable to get GeoJSON strings from EPANET input')

            nodes_geojson, links_geojson = val

            gis_dir = epanet_model_dir / 'gis'
            os.makedirs(gis_dir)

            with open(gis_dir / 'nodes.geojson', 'w') as f:
                json.dump(nodes_geojson, f)

            with open(gis_dir / 'links.geojson', 'w') as f:
                json.dump(links_geojson, f)

            #TODO: for debugging ...
            print('EPANET input file written', file=sys.stderr)

            zip_network_gis(network)

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

    network_path = settings.WMRAT_NETWORK_DIR / str(network.id)

    with open(network_path / 'gis' / 'links.geojson') as f:
        geojson_links = json.load(f)
    with open(network_path / 'gis' / 'nodes.geojson') as f:
        geojson_nodes = json.load(f)

    colors = {
        'PIPE': '#0000ff',
        'PUMP': '#00ff00',
        'VALVE': '#ff0000',
        'JUNCTION': '#000099',
        'RESERVOIR': '#990000',
        'TANK': '#009900',
    }

    context = {
        'page_title': 'WMRat: Explore Network',
        'links': geojson_links,
        'nodes': geojson_nodes,
        'colors': colors,
        'network': network,
    }

    return render(request, 'explore_network.html', context)

@login_required
def new(request):
    success, val = get_analyses_info_dict_with_defaults()
    if not success:
        err_str = val
        return HttpResponseServerError(err_str)

    analyses_info_dict = val

    if request.method == 'POST':
        submitted_dict = request.POST.dict()
        #submitted_dict.pop('csrfmiddlewaretoken')

        network_id = int(submitted_dict['network_id'])

        #XXX: we do not check input (rely on JS validation, but should do that here too)
        analysis_type = submitted_dict['analysis_type']

        arg_dict = {}

        for param_key, param_val in analyses_info_dict[analysis_type]['params'].items():
            if param_val['type'] == 'FLOAT':
                try:
                    val = float(submitted_dict[param_key])
                    arg_dict[param_key] = val
                except ValueError as e:
                    return HttpResponseBadRequest(f'{param_key} must be a floating point number')

            elif param_val['type'] == 'ARRAY':
                vals = submitted_dict[param_key].split(',')
                if len(vals) == 0:
                    return HttpResponseBadRequest(f'{param_key} must be a list of strings')

                vals = list(map(lambda x: x.strip(), vals))

                arg_dict[param_key] = vals

            #TODO: string? probably don't have to support other types ...
        
        #print(arg_dict)

        analysis = Analysis(
            name=submitted_dict['analysis_name'],
            analysis_type=submitted_dict['analysis_type'],
            proc_status=Analysis.STATUS_QUEUED,
            submitted=make_aware(dt.datetime.now()),
            user=request.user,
            duration_s=-1,
            info_msg='Analysis created',
            input_json=arg_dict,
            wm_network=WMNetwork.objects.get(id=network_id),
        )

        analysis.save()

        queue = django_rq.get_queue('crunch')
        job = queue.enqueue(do_run_analysis, analysis)

        analysis.job_id = job.id
        analysis.save()

        return HttpResponseRedirect(reverse('archive', args=()))

    networks = WMNetwork.objects.filter()
    networks = networks.order_by('-uploaded_at')

    context = {
        'page_title': 'WMRat: New Analysis',
        'networks': networks,
        'analyses_info': analyses_info_dict,
    }

    return render(request, 'new.html', context)

@job
def do_run_analysis(analysis):
    then = dt.datetime.now()

    analysis.proc_status = Analysis.STATUS_PROCESSING
    analysis.info_msg = f'Running analysis "{analysis.name}" ...'
    analysis.save()

    analysis_path = settings.WMRAT_ANALYSIS_DIR / str(analysis.id)
    result_dir = analysis_path / 'results'
    if not os.path.exists(analysis_path):
        os.makedirs(analysis_path)
        os.makedirs(result_dir)

    # EPANET file
    epanet_file_path = settings.WMRAT_NETWORK_DIR / str(analysis.wm_network.id) / 'network.inp'

    # param JSON
    input_json_path = analysis_path / 'param.json'
    with open(input_json_path, 'w') as f:
        f.write(json.dumps(analysis.input_json))

    script = settings.TOOLKIT_PATH / 'main.py'
    args = ['python3', script, analysis.analysis_type, epanet_file_path, input_json_path, result_dir]

    #tmp_env = os.environ.copy()
    #tmp_env['EPANET_BIN_PATH'] = settings.EPANET_BIN_PATH
    #p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.PIPE, env=tmp_env)

    p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.PIPE)
    analysis.proc_pid = p.pid
    analysis.save()

    out, err = p.communicate()

    # to get potential status change (user cancelled *running* job)
    analysis.refresh_from_db()

    elapsed_time_s = (dt.datetime.now() - then).total_seconds()
    analysis.duration_s = elapsed_time_s

    if p.returncode != 0:
        if analysis.proc_status == Analysis.STATUS_CANCELLING:
            analysis.proc_status = Analysis.STATUS_CANCELLED
            analysis.info_msg = f'Cancelled'
        else:
            analysis.proc_status = Analysis.STATUS_FAILED
            if elapsed_time_s > settings.MAX_PROCESSING_TIME:
                analysis.info_msg = f'Maximum execution time ({settings.MAX_PROCESSING_TIME}s) exceeded'
            else:
                analysis.info_msg = f'Analysis failed [{p.returncode}]: {err.decode()}'
    else:
        analysis.proc_status = Analysis.STATUS_SUCCESS
        analysis.info_msg = f'Finished'

    zip_analysis(analysis)

    #TODO: maybe delete potential temporary files

    analysis.save()
    return True #NOTE: yes?

def zip_analysis(analysis):
    analysis_path = settings.WMRAT_ANALYSIS_DIR / str(analysis.id)

    new_results_name = f'{analysis.id}_{analysis.name}'.replace(' ', '_')
    zip_name = f'{new_results_name}.zip'

    #XXX: hacky
    os.rename(analysis_path / 'results', analysis_path / new_results_name)

    p = sp.Popen(['zip', '-r', zip_name, new_results_name], stdout=sp.PIPE, stderr=sp.PIPE, cwd=analysis_path)
    out, err = p.communicate()

def zip_network_gis(network):
    network_path = settings.WMRAT_NETWORK_DIR / str(network.id)

    zip_name = f'{network.id}_gis.zip'

    args = ['zip', '-r', zip_name, 'gis']
    p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.PIPE, cwd=network_path)
    out, err = p.communicate()

@login_required
def export_gis(request, network_id):
    network = get_object_or_404(WMNetwork, id=network_id)

    network_path = settings.WMRAT_NETWORK_DIR / str(network.id)

    name = f'{network.id}_gis.zip'
    path = network_path / name

    content_type = 'application/zip'

    resp = HttpResponse(open(path, 'rb'), content_type=content_type)
    resp['Content-Disposition'] = 'attachment; filename={}'.format(name)
    return resp

@login_required
def download_analysis(request, analysis_id):
    analysis = get_object_or_404(Analysis, id=analysis_id)

    analysis_path = settings.WMRAT_ANALYSIS_DIR / str(analysis.id)

    name = f'{analysis.id}_{analysis.name}.zip'.replace(' ', '_')
    path = analysis_path / name

    content_type = 'application/zip'

    resp = HttpResponse(open(path, 'rb'), content_type=content_type)
    resp['Content-Disposition'] = 'attachment; filename={}'.format(name)
    return resp

@login_required
def delete(request, analysis_id):
    scnenario = get_object_or_404(Analysis, id=analysis_id)

    if scnenario.user.id != request.user.id:
        return HttpResponseForbidden('Forbidden')

    scnenario.delete()

    queue = django_rq.get_queue('delete')
    queue.enqueue(do_delete, analysis_id)

    return HttpResponseRedirect(reverse('archive', args=()))

@job
def do_delete(analysis_id):
    analysis_path = settings.WMRAT_ANALYSIS_DIR / str(analysis_id)

    # should exist, but check anyway
    if os.path.exists(analysis_path):
        shutil.rmtree(analysis_path)

@login_required
def cancel(request, analysis_id):
    analysis = get_object_or_404(Analysis, id=analysis_id)

    if analysis.user.id != request.user.id:
        return HttpResponseForbidden('Forbidden')

    # queued, but not run
    if analysis.proc_status == Analysis.STATUS_QUEUED:
        cancel_job(analysis.job_id, connection=django_rq.get_connection('crunch'))
        analysis.proc_status = Analysis.STATUS_CANCELLED
        analysis.info_msg = 'Cancelled'

    # running
    elif analysis.proc_status == Analysis.STATUS_PROCESSING:
        queue = django_rq.get_queue('cancel')
        queue.enqueue(do_cancel, analysis)

        analysis.proc_status = Analysis.STATUS_CANCELLING
        analysis.info_msg = 'Cancelling ...'

    analysis.save()
    return HttpResponseRedirect(reverse('archive', args=()))

@job
def do_cancel(analysis):
    wait_time = 2 #XXX: can do that again?
    try:
        # kill process here (TODO: what if we don't find the pid?)
        # NOTE: we might not have the pid ... ?
        os.kill(analysis.proc_pid, signal.SIGKILL)
    except Exception as e:
        #NOTE: what to do here?
        pass


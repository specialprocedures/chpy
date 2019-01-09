import requests
import re

from fuzzywuzzy import fuzz
from fuzzywuzzy import process

import collections
from pandas.io.json import json_normalize
import json
import math
import time
import networkx as nx
base_url = "https://api.companieshouse.gov.uk"



#####################################
#####################################

def rate_limit(data):
    try:
        if float(data.headers['X-Ratelimit-Remain']) < 10:
            print("Five minute pause for rate limiting.")
            time.sleep(300)
    except KeyError:
        pass

#####################################
#####################################

def format_nums(start_index):
    if start_index >= 1000:
        start_format = str(start_index)[:-3] + "%2C" + str(start_index)[-3:]
    else:
        start_format = str(start_index)
    return(start_format)

#####################################
#####################################

def tabulate_output(data2tabulate):
    table_data = []
    for i in data2tabulate:
        for a in i['items']:
            table_data.append(a)

    return json_normalize(table_data)

#####################################
#####################################

def get_generic(url, api_key):
    ## Pull data
    data = requests.get(url, auth=(api_key, ""))
    ## Run a rate limit check
    rate_limit(data)
    ## If we have good data
    if data.status_code == 200:
        ## Output is in a try/except, as I had some very rare errors crop up.
        try:
            return data.json()
        except JSONDecodeError as e:
            print("Error: JSON")
        ## Errors have an empty list returned for error handling later.
            return []
        else:
            print("Error", data.status_code)
            return []

#####################################
#####################################

def strip_headers(data):
    try:
        return data['items']
    except TypeError:
        return data

#####################################
#####################################

def get_company(number, search_type, api_key):
    if search_type == "profile":
        url = "{}/company/{}".format(base_url, number)
    elif search_type == "officers":
        url = "{}/company/{}/officers".format(base_url, number)
    elif search_type == "psc":
        url = "{}/company/{}/persons-with-significant-control" \
        .format(base_url, number)
    else:
        print("Please specify 'profile', 'officers', or 'psc'")
        return []
    data = get_generic(url, api_key)
    return data

#####################################
#####################################

# def unpack_nested(in_data):
#     if len(in_data) == 1:
#         in_data = [i[0] for i in in_data]
#     return(in_data)

#####################################
#####################################

def get_officer_uid(in_data):
    if 'self' in in_data['links']:
        uid = in_data['links']['self'].split("/")[2]
    elif 'officer' in in_data['links']:
        uid = in_data['links']['officer']['appointments'].split("/")[2]
    else:
        print("Not a vaild record.")
        return
    return uid

#####################################
def prep_for_search(string):
    string = re.sub('[^A-Za-z0-9 ]+', '', string).lower()
    string = string.replace(" ", "+")
    return string
#####################################
#####################################

def get_search_officers(string, api_key, items_per_page = 100, start_index = 0):
    string = prep_for_search(string)
    url = "{}/search/officers?q={}&items_per_page={}&start_index={}" \
    .format(base_url, string, items_per_page, start_index)
    # print(url)
    data = get_generic(url, api_key)
    return data

#####################################
#####################################

def get_officer_appointments(uri, api_key, items_per_page = 100, start_index = 0):
    url = "{}/officers/{}/appointments?items_per_page={}&start_index={}" \
    .format(base_url, uri, items_per_page, start_index)
    data = get_generic(url, api_key)
    return data

#####################################
#####################################

def search_filter(search_results, check_against, thresh = 95):
    out_data = []
    search_results = strip_headers(search_results)
    for search_result in search_results:
        if fuzz.token_sort_ratio(search_result['title'].lower(), check_against['name'].lower()) > thresh:
            search_add = " ".join([i for i in search_result['address'].values()])
            check_add = " ".join([i for i in check_against['address'].values()])
            if fuzz.token_set_ratio(search_add.lower(), check_add.lower()) > thresh:
                out_data.append(search_result)
                continue
            try:
                if search_result['date_of_birth'] == check_against['date_of_birth']:
                    out_data.append(search_result)
                    continue
            except KeyError:
                pass
    return out_data

#####################################
#####################################

def paginate_search(in_data, search_type, api_key, start_index = 0, items_per_page = 100):
    out_data = []

    if search_type == "search":
        query = in_data['name']
        data = get_search_officers(query, api_key, items_per_page, start_index)

    elif search_type == "appointments":
        query = get_officer_uid(in_data)
        data = get_officer_appointments(query, api_key, items_per_page, start_index)

    else:
        print("Please specify 'search' or 'appointments'")
        return

    total_results = data['total_results']

    for iteration in range(math.ceil(total_results/items_per_page)):
        data_len = len(data)
        if search_type == "search":
            data = search_filter(data, in_data)
            try:
                hit_rate = len(data)/data_len
            except ZeroDivisionError:
                hit_rate = 0
        else:
            hit_rate = 1

        out_data.append(data)

        if hit_rate < 0.2:
            break

        start_index = iteration * items_per_page

        if search_type == "search":
            data = get_search_officers(query, api_key, items_per_page, start_index)
        elif search_type == "appointments":
            data = get_officer_appointments(query, api_key, items_per_page, start_index)

    return out_data

#####################################
#####################################


## robbed directly from https://stackoverflow.com/questions/10823877/what-is-the-fastest-way-to-flatten-arbitrarily-nested-lists-in-python

def flatten(container):
    for i in container:
        if isinstance(i, (list,tuple)):
            for j in flatten(i):
                yield j
        else:
            yield i

##################################
##################################

def flatten_appointment_search(appointment_search):
    out_data = []
    for i in appointment_search:
        if len(i) == 1:
            if len(i[0]['items']) == 1:
                out_data.append(i[0]['items'][0])
            else:
                for n, x in enumerate(i[0]['items']):
                    out_data.append(i[0]['items'][n])
        elif len(i) > 1:
            for x in i:
                for n, y in enumerate(x['items']):
                    out_data.append(x['items'][n])
    return out_data

##################################
##################################

def flatten_officer_search(officers):
    flat_officers = []
    for i in officers:
        if len(i) > 1:
            for x in i:
                for z in x:
                    flat_officers.append(z)
        if len(i) == 1:
            for x in i:
                if len(x) == 1:
                    flat_officers.append(x[0])
    return flat_officers

##################################
##################################

# The API has a fair few problems, one of which being that it
# doesn't reliably differentiate human from corporate in the json
# it does manage this admirably well in the name, though. People's
# names are a mix of lower and upper case, companies are all UPPER. #hacking

def human_check(string):
    for i in string:
        if i.islower():
            return "Individual"
    return "Corporate"

##################################
##################################

def make_node_from_officer(item, graph, api_key, thresh = 95):
    # node_fields = ['address', 'identification', 'date_of_birth', 'nationality','country_of_residence']
    item = flatten_dict(item, sep = ".")
    graph.add_node(item['name'])
    if human_check(item['name'])  == "Individual":
        graph.node[item['name']]['node_type'] = "Individual"
        for i in item:
            graph.node[item['name']][i] = item[i]
    # for a in node_fields:
    #     try:
    #         graph.node[item['name']][a] = item[a]
    #     except KeyError:
    #         pass

    elif human_check(item['name'])  == "Corporate":
        graph.node[item['name']]['type'] = "Corporate"
        graph.node[item['name']]['name'] = item['name']
        searched = get_company_search(item['name'], api_key)['items'][0]
        if fuzz.partial_ratio(searched['title'].lower(), item['name'].lower()) > thresh:
            profile = get_company(searched['company_number'], "profile", api_key)
            make_node_from_company(profile, graph)

def make_node_from_company(item, graph):
    item = flatten_dict(item, sep = ".")
    graph.add_node(item['company_name'])
    for i in item:
        graph.node[item['company_name']][i] = item[i]

########################################
#####################################

def get_company_search(string, api_key):
    url = "{}/search/companies?q={}".format(base_url, prep_for_search(string))
    # print(url)
    return get_generic(url, api_key)

#########################################
#########################################

def make_edge_from_appointment(item, graph):
    item = flatten_dict(item, sep = ".")
    graph.add_edge(item['name'], item['appointed_to.company_name'])
    for i in item:
        graph.edges[item['name'], item['appointed_to.company_name']][i] = item[i]

#########################################
#########################################

def make_edge_from_officer(officer, company, graph):
    officer = flatten_dict(officer, sep = ".")
    graph.add_edge(officer['name'], company['company_name'])
    for i in officer:
        graph.edges[officer['name'], company['company_name']][i] = officer[i]




#########################################

### Taken from: https://stackoverflow.com/questions/6027558/flatten-nested-python-dictionaries-compressing-keys




def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

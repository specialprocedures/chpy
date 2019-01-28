import pandas as pd
import re
import collections
from pandas.io.json import json_normalize
import time
from datetime import datetime
from fuzzywuzzy import fuzz, process
"""
Part 1: Helper functions

These functions are small bits of code that help with the smooth flow of
other functions, e.g. rate limiting API calls, unpacking nested data
structures.
"""

def rate_limit(data):
    """
    Expects any JSON pulled from the Companies House API.
    The API provides 600 hits in five minutes, this function checks the headers of
    incoming data and waits if we're running low on hits.

    #roomforimprovement: Currently waits at a five minute sleep when low, could be
    carefully shorter.
    """
    try:
        if float(data.headers['X-Ratelimit-Remain']) < 10:
            wait = abs(datetime.fromtimestamp(int(data.headers['X-Ratelimit-Reset'])) - datetime.now())
            time.sleep(wait.seconds + 10)
            print("Pausing for {} seconds for rate limiting".format(wait.seconds + 10))
    except KeyError:
        pass

def format_nums(start_index):
    """
    Expects an integer.
    Brings numbers exceeding three digits in line with API call requirements
    """
    if start_index >= 1000:
        start_format = str(start_index)[:-3] + "%2C" + str(start_index)[-3:]
    else:
        start_format = str(start_index)
    return(start_format)

def tabulate_output(data2tabulate):
    """
    An old function from a previous version, used for building dataframes from
    nested JSON.

    #depreciate
    """
    table_data = []
    for i in data2tabulate:
        for a in i['items']:
            table_data.append(a)

    return json_normalize(table_data)

def strip_headers(data):
    """ Strips headers from data #depreciate"""
    try:
        return data['items']
    except (TypeError, KeyError) as e:
        print(e)
        return data

def prep_for_search(string):
    """
    Expects a string. Encodes strings in a search-friendy format,
    lowering and replacing spaces with "+"
    """
    string = re.sub('[^A-Za-z0-9 ]+', '', string).lower()
    string = string.replace(" ", "+")
    return string

def flatten(container):
    """
    Expects nested lists, returns iterators. Taken from stackoverflow:
    https://stackoverflow.com/questions/10823877
    """
    for i in container:
        if isinstance(i, (list,tuple)):
            for j in flatten(i):
                yield j
        else:
            yield i

def flatten_dict(d, parent_key='', sep='.'):
    """
    Expects any nested dictionary, returns a (mostly) flattened dictionary
    (see below)

    Flattens nested dictionaries. Taken from stackoverflow:
    https://stackoverflow.com/questions/6027558/

    #roomforimprovement: This is mainly important as networkx can't export
    nested items to gexf. This doesn't yet provide a good way to deal with
    lists, currently taking the crude approach of removing them.
    """
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))

    # Added by me to remove lists, which cause headaches whilst exporting.
    # Lists contain SIC codes and previous company names, which I can
    # pass on for my analysis
    items = [i for i in items if type(i[1]) != list]

    return dict(items)

def get_officer_uid(in_data):
    """
    Extracts an officer's unique identifier from an officer record.
    Unfortunately, lots of officers have lots of these, but the function is
    occasionally useful all the same.
    """
    if 'self' in in_data['links']:
        uid = in_data['links']['self'].split("/")[2]
    elif 'officer' in in_data['links']:
        uid = in_data['links']['officer']['appointments'].split("/")[2]
    else:
        print("Not a vaild record.")
        return
    return uid

def flatten_appointment_search(appointment_search):
    """
    Expects a messy list of appointment searches record from paginate_search().
    Unpacks nested results into one, long manageable list.
    """
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

def flatten_officer_search(officers):
    """
    Expects a messy list of officer searches record from paginate_search().
    Unpacks nested results into one, long manageable list.
    """
    flat_officers = []
    for i in officers:
        try:
            if len(i) > 1:
                for x in i:
                    for z in x:
                        flat_officers.append(z)
            if len(i) == 1:
                for x in i:
                    if len(x) == 1:
                        flat_officers.append(x[0])
        except (TypeError, KeyError) as e:
            print(e)
            pass
    return flat_officers

def human_check(string):
    """
    The API is actually terribly unreliable at providing information on
    whether an entity is human or corporate. What is consistent is that
    companies are provided in UPPER CASE and humans provided in the format
    "SURNAME, Othernames". This takes advantage of this to identify if a
    record is human.
    """
    for i in string:
        if i.islower():
            return "Individual"
    return "Corporate"

def nodes_to_csv(G, company_number):
    out = []
    for node in G.nodes(data = True):
        out.append({"id" : node[0], **node[1]})

    df = json_normalize(out)
    df.to_csv('./data/{}/{}_nodes.csv'.format(company_number, company_number))
    return

def edges_to_csv(G, company_number):
    out = []
    for edge in G.edges(data = True):
        out.append({"source" : edge[0], "target" : edge[1], **edge[2]})
    df = json_normalize(out)
    df.to_csv('./data/{}/{}_edges.csv'.format(company_number, company_number))
    return

def mark_result(item, search_type, iteration = None):
    if item.get("total_results") == 0:
        return item
    else:
        item['query_type'] = search_type
        if search_type == "psc" and item.get('kind') != None:
            if item['kind'] == "corporate-entity-person-with-significant-control":
                item['name'] = item['name'].upper()
        if item.get('address') == None:
            item['address'] = item.get('registered_office_address')
        if item.get('name') == None:
            if item.get('company_name') != None : item['name'] = item.get('company_name')
            if item.get('title') != None : item['name'] = item.get('title')
            if item.get('name') == None : return item
        item['node_type'] = human_check(item['name'])
        item['iteration'] = iteration
        return item

def fuzz_count(col, string):
    return col[col == string].count()                                       ## Counts the occurances of a string in a column

def fuzz_dict(col, tol):
    test = {}
    for i in col.unique():                                                  ## Iterate through everything in the column
        for x in col.unique():                                              ## And do again, nested
            if i != x:                                                      ## If our items are different, we test for similarity
                if fuzz.token_sort_ratio(i, x) > tol:                       ## If the fuzz ratio between the two is higher than cut-off
                    if int(fuzz_count(col, i)) > int(fuzz_count(col, x)):   ## See which is used more often in the column
                        test[i] = i                                         ## Set dict as i if i is more frequent
                    else:
                        test[i] = x                                         ## And also for x
    return test

def clean_dict(x, dct):                                                     ## Just a find and replace with a dictionary for
    try:                                                                    ## applying on a column
        x = dct[x]
    except:
        pass
    return x

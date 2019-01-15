import pandas as pd
import re
import collections
from pandas.io.json import json_normalize
import time

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
            print("Five minute pause for rate limiting.")
            time.sleep(300)
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
        out.append(node[1])
    df = pd.DataFrame(out)
    df.to_csv('./data/{}/{}_nodes.csv'.format(company_number, company_number))
    return

def edges_to_csv(G, company_number):
    out = []
    for edge in G.edges(data = True):
        out.append(edge[2])
    df = pd.DataFrame(out)
    df.to_csv('./data/{}/{}_edges.csv'.format(company_number, company_number))
    return

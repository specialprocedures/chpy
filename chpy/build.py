import os
import progressbar
import networkx as nx
from fuzzywuzzy import fuzz
import pandas as pd

from chpy.utils import *
from chpy.search import *
from chpy.networks import *


def get_company_network(cn_query, api_key):
    """
    This is the main function that ties all the others together to generate
    a network from a given company number. It needs some serious documentation
    which isn't getting done right now.

    #roomforimprovement:
        - document and refactor
        - add psc
        - needs to be directed graph, check functions to see if we're good
    """

    # Make an empty graph into which we'll place our network
    G = nx.Graph()

    hit = cn_query

    # Pull basic information on the ego company and make the first node
    ego_company = get_company(hit, "profile", api_key)
    officers = get_company(hit, "officers", api_key)
    psc = get_company(hit, "psc", api_key)
    make_node_from_company(ego_company, G)

    # Make nodes and edges from company officers
    print("Building network for {}".format(ego_company['company_name']))
    print("Making nodes from initial company officer list")
    with progressbar.ProgressBar(max_value=len(officers['items'])) as bar:
        for n, i in enumerate(officers['items']):
            make_node_from_officer(i, G, api_key)
            make_edge_from_officer(i, ego_company, G)
            bar.update(n)

    # Search for the company's officers. In many cases, one officer will have
    # many records on Companies House.
    print("Searching for Officers")
    with progressbar.ProgressBar(max_value=len(officers['items'])) as bar:
        officer_search = []
        for n, item in enumerate(officers['items']):
            officer_search.append(paginate_search(item, "search", api_key))
            bar.update(n)
        officer_search = flatten_officer_search(officer_search)

    # For each officer, pull a list of their appointments.
    print("Pulling Officer Appointments")
    with progressbar.ProgressBar(max_value=len(officer_search)) as bar:
        appointment_search = []
        for item in officer_search:
            appointment_search.append(paginate_search(item, "appointments", api_key))
            bar.update(n)
        appointment_search = flatten_appointment_search(appointment_search)

    # Pull data for each appointment above and add nodes to graph
    print("Pulling Company Data and Building Graph")
    with progressbar.ProgressBar(max_value=len(appointment_search)) as bar:
        for n, i in enumerate(appointment_search):
            check_list = list(nx.get_node_attributes(G, 'name'))

            ## Checks to see if an appointee is similar to one already in the graph,
            ## if successful, updates the appointee's name to match the graph
            for a in check_list:
                if fuzz.token_sort_ratio(i['name'], a) > 90:
                    i['name'] = a

            ## If the company the appointee is appointed to is not in the node list,
            ## it's added.

            try:
                if i['appointed_to']['company_name'] not in check_list:
                    try:
                        company = get_company(i['appointed_to']['company_number'], "profile", api_key)
                        make_node_from_company(company, G)
                    except (KeyError, TypeError) as e:
                        print("{} not found".format(i['appointed_to']['company_name']))
                        continue
            except (KeyError, TypeError) as e:
                continue

            make_edge_from_appointment(i, G)
            bar.update(n)

    # Get officers from each of the above companies and add to graph
    print("Pulling officers from companies")
    with progressbar.ProgressBar(max_value=len(list(G.nodes))) as bar:
        for n, node in enumerate(list(G.nodes)):
            try:
                if G.nodes[node]['node_type'] == "Corporate":
                    officers = get_company(G.nodes[node]['company_number'], "officers", api_key)
                    for officer in officers['items']:
                            if officer['name'] not in G.nodes:
                                make_node_from_officer(officer, G, api_key)
                                make_edge_from_officer(officer, G.nodes[node], G)
                            elif officer['name'] in G.nodes:
                                make_edge_from_officer(officer, G.nodes[node], G)
            except (KeyError, TypeError, IndexError) as e:
                continue
            bar.update(n)

    # Write graph to disk in gexf format
    os.makedirs('./data/{}/'.format(hit), exist_ok = True)
    nx.write_gexf(G,'./data/{}/{}.gexf'.format(hit, hit))
    nodes_to_csv(G, hit)
    edges_to_csv(G, hit)
    return

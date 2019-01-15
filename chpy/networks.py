import networkx as nx
from chpy.utils import *
from chpy.search import *


def make_node_from_officer(item, graph, api_key, thresh = 95):

    item = flatten_dict(item, sep = ".")

    if human_check(item['name'])  == "Individual":
        # print("Making Individual Node: {}".format(item['name']))
        graph.add_node(item['name'])
        graph.node[item['name']]['node_type'] = "Individual"
        for i in item:
            graph.node[item['name']][i] = item[i]
            graph.node[item['name']]['name'] = item['name']

    elif human_check(item['name'])  == "Corporate":
        # print("Making Corporate Node: {}".format(item['name']))
        searched = get_company_search(item['name'], api_key)['items'][0]
        if fuzz.partial_ratio(searched['title'].lower(), item['name'].lower()) > thresh:
            print("Good fuzz")
            profile = get_company(searched['company_number'], "profile", api_key)
            make_node_from_company(profile, graph)
        else:
            # print("Bad fuzz")
            graph.add_node(item['name'])
            graph.node[item['name']]['node_type'] = "Corporate"
            for i in item:
                graph.node[item['name']][i] = item[i]
                graph.node[item['name']]['name'] = item['name']

def make_node_from_company_name(string, graph, api_key, thresh = 90):
    searched = get_company_search(string, api_key)['items'][0]
    if fuzz.partial_ratio(searched['title'].lower(), string.lower()) > thresh:
        # print("Good fuzz")
        profile = get_company(searched['company_number'], "profile", api_key)
        make_node_from_company(profile, graph)
    else:
        pass

def make_node_from_company(item, graph):
    item = flatten_dict(item, sep = ".")
    graph.add_node(item['company_name'])
    graph.node[item['company_name']]['node_type'] = "Corporate"
    for i in item:
        graph.node[item['company_name']][i] = item[i]
        graph.node[item['company_name']]['name'] = item['company_name']

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

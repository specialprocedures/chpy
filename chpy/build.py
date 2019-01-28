import os
# import progressbar
import networkx as nx
from fuzzywuzzy import fuzz
import pandas as pd

from chpy.utils import *
from chpy.search import *
from chpy.networks import *

def get_company_network(company_number, api_key, depth):
    ## Initial definitions for appending later
    edge_table = []
    dup_list = []
    psc_table = []
    company_table = []
    appointments = []

    # Search for profile of the root company and append to company_table
    root_company = get_company(company_number, "profile", api_key, iteration = 0)
    company_table.append(root_company)

    # Begin pulling down the network
    print("Building network for {}".format(root_company['name']))

    # Outer loop for depth
    for depth_it in range(depth):
        print("Iteration: {} of {}".format(depth_it + 1, depth))
        companies = []

        # Loop through all companies in the company_table
        for n, company in enumerate(company_table):
            # If not already done:
            if company.get('done') != True:

                # Pull officers, pscs and appointments for company
                print("Getting officers, pscs and appointments for {}"
                      .format(company['company_name']))
                officers = get_company(company['company_number'],
                                       "officers", api_key,
                                       iteration = depth_it)
                psc = get_company(company['company_number'],
                                  "psc", api_key, iteration = depth_it)
                psc_table.append(psc)

                '''
                # I'm not sure if there is some duplicate duplication checking,
                but at this stage I can't be bothered to re-write. Here we chain
                a number of functions in chpy.search to retrun a filtered list of
                appointments from a company name, officer list and psc list'''

                if company['name'] not in dup_list:
                    dup_list.append(company['name'])
                    appointments.append(get_appointments(company,
                                                         api_key,
                                                         iteration = depth_it))


                print("Getting officer appointments for {}"
                      .format(company['company_name']))
                officers = [i for i in officers['items']]
                for officer in officers:
                    '''
                    If the officer is a company, we check if it appears in the
                    CH database using a quick fuzz-check. Full filtering isn't
                    used, as addresses are often missing. I've been pretty
                    stringent with the fuzz-check, requiring 99% matching --
                    effectively enough to allow punctuation not to get in the
                    way but little else. If it's in CH, I drop it in for
                    examination in a later pass.
                    '''
                    if human_check(officer['name']) == "Corporate":
                        company_searched = get_company_search(officer['name'], api_key)
                        try:
                            searched_name = company_searched['items'][0]['title']
                        except (IndexError, TypeError, KeyError) as e:
                            searched_name = False

                        if searched_name == officer['name']:
                            searched_num = company_searched['items'][0]['company_number']
                            companies.append(get_company(searched_num, "profile",
                                             api_key, iteration = depth_it))
                            dup_list.append(searched_num)
                    '''
                    Add officer records to the edge_table because sometimes the
                    appointment search misses things.
                    '''
                    officer['source'] = officer['name']
                    officer['target'] = company['name']
                    appointments.append(officer)

                    '''
                    Then we pull each officer's appointments
                    '''
                    if officer['name'] not in dup_list:
                        dup_list.append(officer['name'])
                        appointments.append(get_appointments(officer,
                                                             api_key,
                                                             iteration = depth_it))

                if type(psc) == list or type(psc) == dict:
                    psc = [i for i in psc['items']]
                    print("Getting psc appointments for {}"
                          .format(company['company_name']))
                    for p in psc:
                        if p['name'] not in dup_list:
                            dup_list.append(p['name'])
                            appointments.append(get_appointments(p, api_key,
                                                                 iteration = depth_it))
                else:
                    print("No PSC found")

                # Messy and slow, but needed to filter out any hicoughs that arise.
                appointments = [i for i in flatten(appointments) if type(i) == dict]

                '''
                From all the appointments found, we update a temporary
                companies list to be appended at the end of the iteration cycle.
                '''

                print("Pulling next companies from appointments")
                for appointment in appointments:
                    try:
                        app_num = appointment['appointed_to']['company_number']
                    except (KeyError, TypeError) as e:
                        continue
                    if app_num not in dup_list:
                        companies.append(get_company(app_num, "profile",
                                         api_key, iteration = depth_it))
                        dup_list.append(app_num)

                '''
                Finally, we update the edge_table with all the appointments from
                above. Could be earlier in the function, I guess. Things to look
                at another time.
                '''

                for item in appointments:
                    if item not in edge_table : edge_table.append(item)

                # So we don't do the same company twice.
                company['done'] = True

        '''
        When all the companies in the iteration are done, we update the
        company_table for the next round.
        '''
        company_table.append(companies)
        company_table = [i for i in flatten(company_table) if type(i) == dict]


    '''
    Still a little messy, this bit, but following the pull, we dump the output
    to dataframes and export to csv and gexf.
    '''

    # Step one, build the dataframes we need.
    df = json_normalize([i for i in flatten(edge_table) if type(i) == dict])
    df['company_name'] = df['appointed_to.company_name']
    df['company_number'] = df['appointed_to.company_number']

    ct = json_normalize(company_table)
    psc_df = json_normalize([a for a in flatten([i.get('items')
                             for i in flatten(psc_table)
                             if type(i) == dict
                             and i.get('items') != None])])

    # Bring the fields in the psc dataframe in line with the others
    if len(psc_df) > 0:
        psc_df['company_number'] = psc_df['links.self'].apply(lambda x: x.split("/")[2])
        psc_df = pd.merge(psc_df, ct[['company_number', 'company_name']],
                          on = 'company_number', how = "left")

        # Merge pscs with the main df
        df = pd.concat([df, psc_df], sort = True)

    '''
    We need the names of appointees to be consistent when we build our network.
    In this section, I clean the names, then use fuzzy matching to create a
    dictionary to find/replace similar names.

    It's a bit crude, and has a problem in that it will currently merge two
    different individuals with the same name. Not so much of an issue for those
    interested in the csv output, but a methodolical challenge for the author.
    '''

    df['clean_name'] = df['name'].apply(lambda x: x.replace(" LTD", " LIMITED")
                                        .replace("The Hon", "")
                                        .replace("Dr ", "")
                                        .replace("Mr ", "")
                                        .replace("Mrs ", "")
                                        .replace("Ms ", "")
                                        .replace(".", "").upper())
    clean = fuzz_dict(df['clean_name'], 90)
    df['clean_name'] = df['clean_name'].apply(lambda x: clean_dict(x, clean))
    df['source'] = df['clean_name']

    '''
    Updating the targets where missing (i.e. on pscs). Should have done this
    before merging, oh well, next time.
    '''
    # Silencing an error. Don't worry, it's totally fine :-)
    pd.options.mode.chained_assignment = None
    df['target'].loc[df['target'].isna()] = df['company_name'].loc[df['target'].isna()]

    '''
    Removing some duplicates that arise from using both officers and appointments.
    '''
    df.drop_duplicates(subset=['source', 'target', 'officer_role', 'appointed_on'], inplace = True)


    '''
    Time for graph-building. I'm fairly happy with how the edge-building process
    goes, but ensuring nodes have the right information on them is challenging.
    I'd only recommend using the Gexf for exploration, as this function only
    applies one set of attributes to each node, and will miss things when, for
    example, an individual changes address.
    '''
    # Edges
    edge_list_fields = ['appointed_before',
                    'appointed_on',
                    'appointed_to.company_name',
                    'appointed_to.company_number',
                    'appointed_to.company_status',
                    'ceased_on',
                    'is_pre_1992_appointment',
                    'iteration',
                    'query_type',
                    'officer_role',
                    'notified_on',
                    'resigned_on']
    attribute_list = [i for i in edge_list_fields if i in df.columns]
    G = nx.MultiDiGraph(nx.from_pandas_edgelist(df, 'source',
                                                    'target',
                                                    attribute_list))

    # Nodes
    node_list_fields = ['address.address_line_1', 'address.address_line_2', 'address.care_of',
    'address.country', 'address.locality', 'address.po_box',
    'address.postal_code', 'address.premises', 'address.region',
    'country_of_residence','date_of_birth.month', 'date_of_birth.year',
    'identification.country_registered',
    'identification.identification_type', 'identification.legal_authority',
    'identification.legal_form', 'identification.place_registered',
    'identification.registration_number', 'kind', 'links.self', 'name',
    'name_elements.forename', 'name_elements.honours',
    'name_elements.middle_name', 'name_elements.other_forenames',
    'name_elements.surname', 'name_elements.title', 'nationality',
    'node_type', 'occupation', 'node_type', 'query_type']

    attribute_list = [i for i in edge_list_fields if i in df.columns]

    for row in df.iterrows():
        for item in attribute_list:
            if type(row[1][item]) != list and type(row[1][item]) != dict:
                try:
                    G.nodes[row[1]['source']][item] = row[1][item]
                except KeyError:
                    continue

    for row in ct.iterrows():
        for item in ct.columns:
            if type(row[1][item]) != list and type(row[1][item]) != dict:
                try:
                    G.nodes[row[1]['company_name']][item] = row[1][item]
                except KeyError:
                    continue
    
    # Write everything to disk
    file_id = "{}_{}".format(company_number, depth)
    os.makedirs('./data/{}/'.format(file_id), exist_ok = True)
    nx.write_gexf(G,'./data/{}/{}.gexf'.format(file_id, file_id))
    df.to_csv('./data/{}/{}_edge_list.csv'.format(file_id, file_id))
    ct.to_csv('./data/{}/{}_companies.csv'.format(file_id, file_id))

    return G, df, ct



# def get_company_network(cn_query, api_key):
#     """
#     This is the main function that ties all the others together to generate
#     a network from a given company number. It needs some serious documentation
#     which isn't getting done right now.
#
#     #roomforimprovement:
#         - document and refactor
#         - add psc
#         - needs to be directed graph, check functions to see if we're good
#     """
#
#     # Make an empty graph into which we'll place our network
#     G = nx.Graph()
#
#     hit = cn_query
#
#     # Pull basic information on the ego company and make the first node
#     ego_company = get_company(hit, "profile", api_key)
#     officers = get_company(hit, "officers", api_key)
#     psc = get_company(hit, "psc", api_key)
#     make_node_from_company(ego_company, G)
#
#     # Make nodes and edges from company officers
#     print("Building network for {}".format(ego_company['company_name']))
#     print("Making nodes from initial company officer list")
#     with progressbar.ProgressBar(max_value=len(officers['items'])) as bar:
#         for n, i in enumerate(officers['items']):
#             make_node_from_officer(i, G, api_key)
#             make_edge_from_officer(i, ego_company, G)
#             bar.update(n)
#
#     # Search for the company's officers. In many cases, one officer will have
#     # many records on Companies House.
#     print("Searching for Officers")
#     with progressbar.ProgressBar(max_value=len(officers['items'])) as bar:
#         officer_search = []
#         for n, item in enumerate(officers['items']):
#             officer_search.append(paginate_search(item, "search", api_key))
#             bar.update(n)
#         officer_search = flatten_officer_search(officer_search)
#
#     # For each officer, pull a list of their appointments.
#     print("Pulling Officer Appointments")
#     with progressbar.ProgressBar(max_value=len(officer_search)) as bar:
#         appointment_search = []
#         for item in officer_search:
#             appointment_search.append(paginate_search(item, "appointments", api_key))
#             bar.update(n)
#         appointment_search = flatten_appointment_search(appointment_search)
#
#     # Pull data for each appointment above and add nodes to graph
#     print("Pulling Company Data and Building Graph")
#     with progressbar.ProgressBar(max_value=len(appointment_search)) as bar:
#         for n, i in enumerate(appointment_search):
#             check_list = list(nx.get_node_attributes(G, 'name'))
#
#             ## Checks to see if an appointee is similar to one already in the graph,
#             ## if successful, updates the appointee's name to match the graph
#             for a in check_list:
#                 if fuzz.token_sort_ratio(i['name'], a) > 90:
#                     i['name'] = a
#
#             ## If the company the appointee is appointed to is not in the node list,
#             ## it's added.
#
#             try:
#                 if i['appointed_to']['company_name'] not in check_list:
#                     try:
#                         company = get_company(i['appointed_to']['company_number'], "profile", api_key)
#                         make_node_from_company(company, G)
#                     except (KeyError, TypeError) as e:
#                         print("{} not found".format(i['appointed_to']['company_name']))
#                         continue
#             except (KeyError, TypeError) as e:
#                 continue
#
#             make_edge_from_appointment(i, G)
#             bar.update(n)
#
#     # Get officers from each of the above companies and add to graph
#     print("Pulling officers from companies")
#     with progressbar.ProgressBar(max_value=len(list(G.nodes))) as bar:
#         for n, node in enumerate(list(G.nodes)):
#             try:
#                 if G.nodes[node]['node_type'] == "Corporate":
#                     officers = get_company(G.nodes[node]['company_number'], "officers", api_key)
#                     for officer in officers['items']:
#                             if officer['name'] not in G.nodes:
#                                 make_node_from_officer(officer, G, api_key)
#                                 make_edge_from_officer(officer, G.nodes[node], G)
#                             elif officer['name'] in G.nodes:
#                                 make_edge_from_officer(officer, G.nodes[node], G)
#             except (KeyError, TypeError, IndexError) as e:
#                 continue
#             bar.update(n)
#
#     # Write graph to disk in gexf format
#     os.makedirs('./data/{}/'.format(hit), exist_ok = True)
#     nx.write_gexf(G,'./data/{}/{}.gexf'.format(hit, hit))
#     nodes_to_csv(G, hit)
#     edges_to_csv(G, hit)
#     return

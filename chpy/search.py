import requests
from fuzzywuzzy import fuzz

import math
import time                                      ## For rate limiting

from chpy.utils import *


base_url = "https://api.companieshouse.gov.uk"

def get_generic(url, api_key):
    """
    Workhorse generic API call function. Relies on other functions to
    generate complete call urls, then applies rate limiting and error-checking.
    """

    # print(url)
    data = requests.get(url, auth=(api_key, ""))
    rate_limit(data)

    if data.status_code == 200:
        ## Output is in a try/except, as I had some very rare errors crop up.
        try:
            return data.json()
        except JSONDecodeError:
            # print("Error: JSON")
            # data = {"total_results" : 0, "fail" : True}
            return
    elif data.status_code == 502:
        for i in range(1,10):
            data = requests.get(url, auth=(api_key, ""))
            if data.status_code == 200:
                ## Output is in a try/except, as I had some very rare errors crop up.
                try:
                    return data.json()
                except JSONDecodeError:
                    # print("Error: JSON")
                    # data = {"total_results" : 0, "fail" : True}
                    return
            else:
                pass
        return
    else:
        # print("Error", data.status_code)
        # print(url)
        # print(data)
        # data = {"total_results" : 0, "fail" : True}
        return

def get_company(number, search_type, api_key, iteration = None):
    """
    Multi-functional function to get data from a known company number.
    search_type expects:
        - "profile": returning a company profile
        - "officers": returning a list of company officers
        - "psc": returning persons of significant control
    """
    if search_type == "profile":
        url = "{}/company/{}".format(base_url, number)
    elif search_type == "officers":
        url = "{}/company/{}/officers".format(base_url, number)
    elif search_type == "psc":
        url = "{}/company/{}/persons-with-significant-control" \
        .format(base_url, number)
    else:
        print("Please specify 'profile', 'officers', or 'psc'")
        return

    data = get_generic(url, api_key)

    try:
        if data.get("items") != None:
            for item in data['items']:
                mark_result(item, search_type, iteration = iteration)
        else:
            mark_result(data, search_type, iteration = iteration)
    except AttributeError:
        return
    return data

##################





def get_search_officers(string, api_key, items_per_page = 100, start_index = 0):
    """
    Searches for company officers based on a string, returns an OfficerSearch
    resource. Later used by paginate_search() and search_filter() to trawl
    through multiple pages of potential hits.
    """

    s_string = prep_for_search(string)
    url = "{}/search/officers?q={}&items_per_page={}&start_index={}" \
    .format(base_url, s_string, items_per_page, format_nums(start_index))
    # print(url)

    data = get_generic(url, api_key)

    # if data['total_results'] == 0:
    #     print("No results found for {}".format(string))
    #     return data
    # else:
    return data

def get_officer_appointments(uri,
                             api_key,
                             items_per_page = 100,
                             start_index = 0):
    """
    Returns an appointmentList resource based on an officer's uri. Used by
    paginate_search().

    #roomforimprovement: This could actually be fed most of the url directly
    without calling the get_officer_uid() function.
    """
    url = "{}/officers/{}/appointments?items_per_page={}&start_index={}" \
    .format(base_url, uri, items_per_page, format_nums(start_index))
    data = get_generic(url, api_key)
    return data

def search_filter(search_results, check_against, thresh = 90):
    """
    A critical function which works to address the absence of effective uids
    for officer appointment resources. It matches search results with
    (most frequently) officer records, enabling the creation of links between
    two entities on the basis of a search result. It has three key steps:
        1) Check if there is a good fuzzy match (token_sort_ratio) between
           the names of both records.
        2) Perform a fuzzy match (token_set_ratio) on the addresses of both
           entities.
        3) If present, check for matching dates of birth.

    In pseudo-code:
        IF names fuzzymatch AND addresses fuzzymatch (AND date_of_birth matches)

    #roomforimprovement:
        - This function was written before human_check(), and could be enhanced
          by it, automatically performing different checks on the basis of
          entity-type (i.e. "Individual" or "Corporate").
        - It could provide some form of confidence score in the reult provided.
        - It is currently configured with a conservative sampling methodology
          in mind, additional options (aside from the threshold) could be
          provided to relax criteria.

    Limitations
    There will always be issues with this function, particularly where
    individuals, rather than companies, are involved. The issue is serious
    and stems from data-quality. If, for example, user input data gives
    inconsistent dates of birth across records, or (more likely) an individual
    provides different addresses across records, they will be rejected.

    A decision has been made to make this function conservative in what it
    accepts (i.e. favouring false negatives over false positives). This is for
    a number of reasons:
        - The primary purpose of chpy is to support my research for my
          masters' thesis, and I wish to keep my results as "tame" as possible.
          I feel this approach will lead to less distored sampling.
        - A more "relaxed" approach will lead to larger networks, which can
          grow exponentially with additional nodes. This keeps things more
          manageable, as well as being more methodologically sound.
        - Being too open presents serious issues of false positivity, for
          example where an officer is called "John Smith", significant
          numbers of false positives could be found.
    """
    out_data = []

    # try:
    #     if search_results['total_results'] == 0:
    #         return
    # except TypeError:
    #     print(search_results)

    search_results = strip_headers(search_results)

    for search_result in search_results:
        ## Name check vs. fuzz
        name_check = fuzz.token_sort_ratio(
        search_result['title'].lower(),
        check_against['name'].lower()) > thresh

        search_add = " ".join(
        [i for i in search_result['address'].values()])
        check_add = " ".join(
        [i for i in check_against['address'].values()])

        add_check = fuzz.token_set_ratio(search_add.lower(), check_add.lower()) > thresh

        try:
            dob_check = search_result['date_of_birth'] == check_against['date_of_birth']
        except (TypeError, KeyError) as e:
            dob_check = False


        if (name_check and add_check) or (name_check and dob_check):
            out_data.append(search_result)

    return out_data

def paginate_search(in_data,
                    search_type,
                    api_key,
                    start_index = 0,
                    items_per_page = 100):
    """
    Another large and important function. This paginates through resources
    that are returned across multiple pages (i.e. search results and
    officer appointments).

    Expects either an officer list generated by get_company(number, "officers")
    or an appointments list id, generated from an officer resource.

    Requests search_type:
        - "search": performs an officer search, returning an officer search
                    resource
        - "appointments": retrieves a list of company appointments for a given
                    uid (based on an officer resource).

    #roomforimprovement:
        - It's not actually necessary to call the get_officer_uid() function
          here, as it'd be more efficient to skip this step and send the
          relevant field directly to get_officer_appointments().
        - The 0.2 figure provided in hit_rate is arbritrary, and could be
          passed as an argument to the function.
        - There's repetition during the data-pull that could be ironed out
          into a separate function.
        - I've got suspicion that manually defining the search type isn't
          necessary.
        - I should probably find a way to integrate the get_company_search()
          function.
    """

    out_data = []

    # Set type of search and call appropriate function.
    if search_type == "search":
        query = in_data['name']
        # print("SRCHQ: ", query)
        data = get_search_officers(query, api_key,
                                   items_per_page, start_index)

    elif search_type == "appointments":
        query = get_officer_uid(in_data)
        # print("APPT Q: ", query)
        data = get_officer_appointments(query, api_key,
                                        items_per_page, start_index)

    else:
        print("Please specify 'search' or 'appointments'")
        return

    # if data['total_results'] == 0:
    #     return data

    # Pull total number of results from header.
    total_results = data['total_results']
    if total_results == 0:
        return
    # Iterate through the number pages required (identified by dividing the
    # total_results by items_per_page)
    total_pages = math.ceil(total_results/items_per_page)
    for iteration in range(total_pages):
        # try:

        data_len = len(data['items'])

        # except (TypeError, KeyError) as e:
        #     print("Insufficient information for search")
        #     return
        if search_type == "search":
            filtered_data = search_filter(data, in_data)
            # For the "search" type, we'll start running out of "good" results
            # at some point. This try/except block gives up when we stop getting
            # a reasonable amount of hits.
            try:
                hit_rate = len(filtered_data)/data_len
            except ZeroDivisionError:
                hit_rate = 0

            for item in filtered_data:
                if item not in out_data:
                    out_data.append(item)
        # If it's not a search, it's an appointment list, which requires
        # pagination to the end of the list, in which case we maintain the
        # hit rate at 1.
        else:
            out_data.append(data)
            hit_rate = 1

        if hit_rate < 0.2:
            break

        if iteration == 0:
             continue

        start_index = iteration * items_per_page

        if search_type == "search":
            data = get_search_officers(query, api_key, items_per_page, start_index)
        elif search_type == "appointments":
            data = get_officer_appointments(query, api_key, items_per_page, start_index)

        # try:
        #     if data['total_results'] == 0:
        #         break
        # except (TypeError, KeyError) as e:
        #     break
    return out_data

def get_appointments(node, api_key, iteration = 0):
    out_data = []
    dup_list = []
    try:
        if node.get('query_type') == "officers":
            listed_appts = list(flatten(paginate_search(node, "appointments", api_key)))
            dup_list.append(listed_appts[0]['links']['self'])
            for appointment in listed_appts[0]['items']:
                appointment = mark_result(appointment, "appointment", iteration = iteration)
                appointment['source'] = appointment['name']
                appointment['target'] = appointment['appointed_to']['company_name']
                appointment['date_of_birth'] = listed_appts[0].get('date_of_birth')
                out_data.append(appointment)
    except (KeyError, AttributeError, TypeError) as e:
        pass

    try:
        appt_search = list(flatten(paginate_search(node, "search", api_key)))
    except TypeError as e:
        return

    for appt in appt_search:
        if appt['links']['self'] not in dup_list:
            appointments = list(flatten(paginate_search(appt, "appointments", api_key)))
            for appointment in appointments[0]['items']:
                if fuzz.token_sort_ratio(node['name'], appointment['name']) < 90:
                    continue
                else:
                    appointment = mark_result(appointment, "appointment", iteration = iteration)
                    appointment['source'] = appointment['name']
                    appointment['target'] = appointment['appointed_to']['company_name']
                    appointment['date_of_birth'] = appointments[0].get('date_of_birth')
                    out_data.append(appointment)
    return out_data

def get_company_search(string, api_key):
    """
    Performs a basic, unpaginated (i.e. one page) search for a company by its
    name. Crude, but needed for something in the network component.

    #roomforimprovement: Needs to be integrated into the pagination component.
    """
    url = "{}/search/companies?q={}".format(base_url, prep_for_search(string))
    return get_generic(url, api_key)

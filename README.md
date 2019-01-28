# chpy
A wrapper for the UK Companies House API, written in Python with tools for network analysis built on networkx.

# Notes
This tool enables users to build a corporate network from information on the UK Companies House API.
Networks are constructed through the following process:
- The user inputs a valid UK company number, alongside an API key and a number of desired iterations.
- From this company, chpy draws down information on its officers and persons of significant control (PSC).
- Relationships between officers/PSC and the company being searched are added to an edge list.
- If an officer is a valid UK company, it is added to a list of companies for examination in later iterations. NB: In 0.1.1a, this functionality does not extend to PSCs.
- chpy then searches the Companies House API for each officer/PSCs appointments to other companies, using fuzzy matching and date of birth/address checks to verify search results.
- These relationships are then added to the edge list, and the companies added to the company table for analysis in later iterations.
- The process loops to a depth specified by the user.

# New in 0.1.1
- The main function -- get_company_network() -- has been completely overhauled with:
  - A new, clearer structure for data acquisition.
  - Iteration depth.
  - Output to networkx graph and pandas dataframes from within Python.
  - Clearer output whilst running, however progress bar functionality has been suspended for the time being.

# How it works
  ![alt text](https://raw.githubusercontent.com/specialprocedures/chpy/master/images/chpy_0_1_1a.gif)

# Usage
This tool is currently intended for use alongside a Jupyter notebook, and I've provided a sample in the "example" directory.
I believe that most users will want to do with this is simply build a network from a company that they have interest in.
It is strongly recommended that the depth is set to either 1 or 2. Depth scales exponentially, as will errors (see "A word of warning", below).


```
pip install chpy
```

```
from chpy.build import *

# You'll need your own API key from Companies House and to load
# it as a variable in Python.
with open('API_KEY.txt') as f:
    api_key = f.read().strip()

graph, edge_list, company_table = get_company_network("a valid company number", api_key, 2)
```

The above code returns a graph in networkx format, and an edge_list and company_table as Pandas dataframes.

Additionally, chpy outputs three objects to ./data/company_number_depth/:
- One node list in csv format
- One edge list in csv format
- One graph in gexf format, for use with gephy or similar

# A word of warning
This is very much still in development, and due to the way Companies House (CH) data is maintained and structured a degree of caution is required when using this tool. Notably:
- CH does not maintain information on companies that have been wound up for a certain period of time, so be aware that in many cases the data produced will be incomplete.
- Similarly, inactive officers are not always available.
- This software makes extensive use of fuzzy matching to build links between companies and officers, due to the limitations of the unique identifier system used by the CH API. The system is designed to be conservative with the relationships it builds, requiring date of birth (if available) and location matches, and as such may miss relationships if a strong match isn't found.
- Similarly, given the use of the CH search API and fuzzy matching, despite the safeguards outlined above, "false positives" may still occur in exceptional circumstances.

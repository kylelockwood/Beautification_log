#! python3

import os, sys
import re
import json
import zipfile
import time
import datetime
from datetime import datetime as dt
import csv
import openpyxl
import pandas as pd
import matplotlib.pyplot as plt
import requests
import curses



class Beautification_Stats():
    def __init__(self, param_file):
        # TODO Can Google Address Validation return city state and zip separately when validating to avoid having to manually extract with unreliable .split() method?
        # TODO Additive databse so you don't have to redo the whole dataset everytime, just the changes.
        # TODO More and better error checking and reporting
        # TODO Use curses to clean up interface, try to make this useable by most anyone
        # TODO The whole thing is wrapped in a try block for terminal error output purposes. Debugging will be caught and displayed if self.vars calls for it. Turn this on when the script is complete, as it will create less verbose error language.

        # Store the Google Address Validation API token as an environmetental variable
        # Remember to restart the python environment when making changes to global variables
        self.GoogleAPI = os.environ.get('GoogleAPI')
        
        # Set variables
        self.scriptpath = os.path.dirname(os.path.realpath(sys.argv[0])) + '\\'
        self.vars = self.load_json(param_file)
        self.dataset = {}
        
        # Check if dataset already exists in scriptpath
        existing_dataset = self.find_latest_file(self.scriptpath, 'outfile')
        
        options = ['New dataset']
        title = None
        if existing_dataset:
            title = f'Existing dataset found : "{existing_dataset}"'
            options.append('Import existing dataset') 
            options.append('Update existing dataset')                        
        options.append('Quit')
    
        user_input = highlight_options(options, curses.initscr(), title=title)
        curses.endwin()
        
        os.system('cls')

        if user_input == 0:
            self.new_dataset()
        elif user_input == 1:
            self.import_dataset(existing_dataset)
        elif user_input == 2:
            self.update_dataset(existing_dataset)        
        else:
            sys.exit()  
    
        # Create readable output based on user parameters
        Report(self.dataset, self.vars['report_options'])

        # Used for terminal error display to make it more friendly in the end app
        #except Exception as e:
           # print(e)

    def load_json(self, filename):
        """Return data from JSON file as a dict"""
        try:
            with open(self.scriptpath + filename) as f:
                data = json.load(f)
        except Exception as e:
            sys.exit('Unable to load JSON data from "' + filename + '". ' + str(e))
        return data

    def return_paths(self, searchkeyword):
        """Find the file to be edited"""
        homepath = 'C:' + os.environ["HOMEPATH"]
        searchpath = self.vars[searchkeyword]["path"]
        if not searchpath.startswith('C:'):
            searchpath = homepath + '\\'+ searchpath +'\\'
        return searchpath

    def find_latest_file(self, searchpath, key=None):
        """Return the most recent file matching search criteria"""
        searchfile = self.vars[key]["namekeyword"]
        if '.' in searchfile:
            searchfile = searchfile.split('.')[0]
        searchtype = self.vars[key]["type"]
        allfiles = os.listdir(searchpath)
        matchfiles = [os.path.join(searchpath, basename) for basename in allfiles if basename.endswith(searchtype) and searchfile in basename]
        try:
            foundfile = max(matchfiles, key=os.path.getctime)
        except ValueError:
            if key == 'outfile':
                return None
            else:
                print(f'\n\nCould not find a {searchtype} file containing "{searchfile}" in folder "{searchpath}". Ensure that you have downloaded the correct file, or adjust variable.json search parameters.')
                p = sys.exit(input())
        return foundfile

    def new_dataset(self, date_range=None):
        data_sets = [] 
        
        # TODO this should probably be broken out to return individual data sets for updating the existing dataset

        for key in self.vars:
            try:
                # Replace 'scriptpath' str in json with actual script path
                if self.vars[key]['path'] == 'scriptpath':
                    self.vars[key]['path'] = self.scriptpath

                # Replace 'path' keyword with full path
                self.vars[key]['path'] = self.return_paths(key)

                # Add full file path of latest file matching key to ['file']
                self.vars[key]['file'] = self.find_latest_file(self.vars[key]['path'], key)

                # If the latest file is a zip file, get a list of the files within, extract them, and change the 'file' to the first file in the zip folder.
                if (self.vars[key]['file']).endswith('.zip'):
                    zfile = self.vars[key]['file']
                    print(f'\nExtracting file(s) from .zip folder "{zfile}"... ', end='', flush=True)
                    
                    # Note, Windows 10 extracts the file, while Windows 11 extracts the folder.
                    # TODO This needs to account for all .zip behaviors
                    # Workaround is to extract the file manually and change the variabels.json[key]['type'] to the file type instead of .zip
                    with zipfile.ZipFile(zfile, 'r') as zip_ref:
                        zip_ref.extractall(self.vars[key]['path'])
                        self.vars[key]['type'] = '.' + zip_ref.namelist()[0].split('.')[-1]
                        self.vars[key]['file'] = self.find_latest_file(self.vars[key]['path'], key)
                    print('Done')

                # Add data to files that are "read_files"
                if self.vars[key]['read_file']:
                    # Add the creation date of the file to ['cdate']
                    cdate = os.path.getctime(self.vars[key]['file'])
                    cdate = dt.strptime(time.ctime(cdate),'%a %b %d %H:%M:%S %Y')
                    self.vars[key]['cdate'] = dt.strftime(cdate, '%Y%m%d')
                    
                    # Add data to the key dependant on type
                    if self.vars[key]['type'] == '.csv':
                        self.vars[key]['data'] = self.get_csv_data(key)
                        
                    elif self.vars[key]['type'] == '.xlsx':
                        self.vars[key]['data'] = self.get_xlsx_data(key)

                # Create a list of tuples from 'clean_index' to tell self.sanitize what data to scrub
                cleanlist = []
                for clean in self.vars[key]['clean_index']:
                    #print(clean)
                    for k, v in clean.items():
                        cleanlist.append((v, k))

                # Sanitize the data as specified in the cleanlist
                self.sanitize(self.vars[key], cleanlist) # TODO Sanitize addresses
                
                # Create headers for output csv
                headers = self.vars[key]['headers'] = [self.vars[key]['namekeyword'] + '_' + head for head in self.vars[key]['data_cols']]
                #print(f'{headers=}')

                # Totals and percentages for each date, and add appropriate headers
                self.vars[key]['data'] = self.date_lbs_totals(self.vars[key], self.vars[key]['data_index']['weight']) 

                # Add var names to list of datasets 
                data_sets.append(key)

            except KeyError:
                continue

            except PermissionError:
                file = self.vars[key]['file']
                sys.exit(input(f'\n\nError : Cannot access "{file}", it is likely open. Please close the file and try again.'))

        # Create a new csv file combining the sanitized data from all files using parameters set in vars['outfile']          
        self.create_dataset(data_sets)
        
        # Add city, state, zip to dataset. This had to be done after initial dataset creation for build purposes and can be fixed later if necessary.
        self.parse_addresses(self.dataset, 2) # Index of addresses in dataset

        # Write the sanatized dataset to a file, open it if ['outfile']['openfile'] is true
        self.write_csv(self.dataset['headers'], self.dataset['data'], self.vars['outfile']['openfile'])

    def import_dataset(self, existing_dataset):
        self.vars['outfile']['file'] = existing_dataset
        self.dataset['data'] = self.get_csv_data('outfile')
        # Create ['headers'] from first row of data, then remove that row from ['data']
        self.dataset['headers'] = [head for head in self.dataset['data'][0]]
        self.dataset['data'].pop(0)

    def update_dataset(self, existing_dataset):
        # TODO Find the date range in the existing dataset
        # TODO Start a new dataset only pulling data in a date_range start to now() or whatever
        # TODO Write a new csv with this data (don't replace the old one)
        raise NotImplementedError 

    def get_csv_data(self, key):
        filename = self.vars[key]['file']
        print(f'\nParsing csv data in "{filename}"... ', end='', flush=True)
        filtered_data = []

        with open(filename, 'r', encoding='utf-8') as csvfile:
            csvreader = csv.reader(csvfile)
            header = next(csvreader)

            # Get the indices of the desired columns based on 'data_cols'
            desired_indices = [idx for idx, col_name in enumerate(header) if col_name in self.vars[key]['data_cols']]

            # Extract the desired columns from the header
            filtered_header = [header[idx] for idx in desired_indices]
            filtered_data.append(filtered_header)

            # Extract the desired columns from each row
            for row in csvreader:
                filtered_row = [row[idx] for idx in desired_indices]
                filtered_data.append(filtered_row)
        print('Done')
        return filtered_data
            
    def get_xlsx_data(self, key):
        filename = self.vars[key]['file']
        print(f'\nParsing xlsx data in "{filename}"... ', end='', flush=True)
        workbook = openpyxl.load_workbook(filename)
        column_headers = self.vars[key]['data_cols']
        all_sheets_data = []

        for sheet in workbook.worksheets:
            column_indices = []

            for header in column_headers:
                for cell in sheet[1]:  # Row 1 contains the column headers
                    if cell.value == header:
                        column_indices.append(cell.column - 1)  # Subtract 1 to get zero-based index
                        break

            for row in sheet.iter_rows(min_row=2):  # Start from row 2 to exclude headers
                row_data = [row[index].value for index in column_indices]

                # Check if any value in row_data is a datetime object or a float
                if any(isinstance(value, (dt, float, int)) for value in row_data):
                    all_sheets_data.append(row_data)
                else:
                    continue

        print('Done.')
        return all_sheets_data
    
    def sanitize(self, key, cleanlist):        
        """Standardize data
        Pass vars[key], and list of tuples containing data index sanitize type, e.g. [(2, 'weight'), (1, 'address')]
        Accepted sanitize type args are: 'date', 'weight', 'address', 'meals'
        """
        sanitizer_functions = {
            'Weight': self.weight_sanitize,
            'Address': self.address_sanitize,
            'Meals': self.meals_sanitize,
            'Date' : self.date_sanitize,
        }

        for clean in cleanlist:
            data_index = clean[0]
            sanitizer_type = clean[1]

            # Get the appropriate function based on the sanitizer_type
            sanitizer_function = sanitizer_functions.get(sanitizer_type)

            # Sanitize that data!
            if sanitizer_function:
                print(f'\n``` Sanitizing data :  ', end='', flush=True)
                print(sanitizer_type + ' ```')
                key['data'] = sanitizer_function(key['data'], data_index)
            else:
                print(f"No sanitizer function found for {sanitizer_type}")

    def weight_sanitize(self, data, data_index):
        """
        Standardize weights to lbs for calculations
        Convert keywords in the dataset from list in self.vars['convert']['to_lbs'] to weight values
        Uncaught errors ask for user input correction
        """

        bad_data = False # This toggles user input for data that isn't caught by convert_to_lbs keys
        flag = False # For checking removed data
        
        convert_to_lbs = self.vars['convert']['to_lbs']

        # Create a regex pattern for each keyword in convert_to_lbs.keys()
        patterns = [r'(\d+)\s*{0}s?'.format(keyword.replace(" ", r"\s")) for keyword in convert_to_lbs.keys()]

        # Combine patterns with '|', meaning 'or'
        combined_pattern = '|'.join(patterns)

        for item in data:
            try:
                weight = item[data_index]
                #print(f'{weight=}')
                if isinstance(weight, int) or isinstance(weight, float):
                    #print(f'INT OR FLOAT {weight=}  {type(weight)=}')
                    continue
                if not weight:
                    #print(f'NOT WEIGHT {weight=}')
                    item[data_index] = 0
                else:
                    #print(f'    WEIGHT STR {weight=}    {type(weight)=}')
                    weight = weight.strip()  # Strip the string to remove spaces at the beginning and end
                    total_weight = 0
                    is_half = 'half' in weight.lower()
                    if weight.isdigit():
                        total_weight = int(weight)
                    else:
                        for keyword, conversion_factor in convert_to_lbs.items():
                            # Match the keywords in conver_to_lbs with the data, convert based on the value and return an integer
                            pattern = r'(\d*)\s*{0}s?'.format(keyword.replace(" ", r"\s"))
                            match = re.search(pattern, weight.lower())
                            if match:
                                num_items = match.group(1)
                                num_items = int(num_items) if num_items else 1  # Assume 1 item if there's no number
                                if is_half:
                                    num_items *= 0.5
                                total_weight += num_items * conversion_factor
                    if total_weight > 0:
                        item[data_index] = total_weight
                        #print(f'    {item[data_index]=}')
                    else:
                        # User fix data that is not caught by convert_to_lbs
                        if not bad_data:
                            print('\nUnrecognized data found, please enter a weight in pounds (integer only) for each item,:')
                            bad_data = True
                        while True:
                            try:
                                user_input = input(f'Enter approximate pounds for "{item[data_index]}" or press <ENTER> to delete row : ')
                                if user_input == "":
                                    data.remove(item)
                                    print('    row removed from dataset')
                                    flag = True
                                    break
                                item[data_index] = int(user_input)
                                break
                            except ValueError:
                                print("Invalid input. Please enter an integer.")
                        #print(f'other {item[data_index]=}')
                        
            except ValueError as e:
                print('error : ' + str(e))
                continue
            except TypeError as e:
                print('error : ' + str(e))
                continue

        # If a row is deleted from the dataset, the next index will be skipped, this runs through the dataset again to make sure the skipped row is sanitized as well
        if flag:
            data = self.weight_sanitize(data, data_index)
        #sys.exit()
        return(data)        
   
    def address_sanitize(self, data, data_index, counter=1):
        total = len(data)
        for item in data:
            print(f'Correcting addresses... {counter} of {total}', end='\r', flush=True)
            address = item[data_index]
            item[data_index] = self.check_address(address, counter)
            # If check_address returns None remove the item
            if not item[data_index]:
                data.remove(item)
            counter += 1
        # City and state get added later. This is because I don't want to mess with the data order and I did addresses last because I had to wait for the Google API key to be approved.
        return data

    def check_address(self, address, counter, flag=False):
        url = f'https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={address}&inputtype=textquery&fields=formatted_address&key={self.GoogleAPI}'
        response = requests.get(url)
        json_data = response.json()
        if json_data['status'] == 'OK':
            return json_data['candidates'][0]['formatted_address']           
        else:
            if not flag:
                address += ', Portland, OR' # Vast majority of addresses are in Portland. This is to help push the user data in the right direction and will fix most instances. However, it may cause some data inaccuracy and may need to be removed.
                return self.check_address(address, counter, flag=True)

            if flag:
                user_input = input(f'\nDo not understand address "{address}", enter corrected address or press <ENTER> to remove from dataset : ')
                if not user_input:
                    print('\n  row removed from dataset')
                    return None
                else:
                    return self.check_address(user_input, counter)


        """
        # TODO This code (gpt gen) returns the components of the address rather than the entire address which will make for more accurate data
        # Set the API endpoint and parameters
        endpoint = 'https://maps.googleapis.com/maps/api/geocode/json'
        params = {
            'address': '123 SE Ash St. Portland, OR',
            'key': 'YOUR_API_KEY'  # Replace with your own API key
        }

        # Send a GET request to the API endpoint and parse the response
        response = requests.get(endpoint, params=params)
        data = json.loads(response.text)

        # Extract the street address, city, state, ZIP code, and county from the formatted address
        formatted_address = data['results'][0]['formatted_address']
        components = formatted_address.split(', ')
        street_address = components[0]
        city = next(c['long_name'] for c in data['results'][0]['address_components'] if 'locality' in c['types'])
        state = next(c['short_name'] for c in data['results'][0]['address_components'] if 'administrative_area_level_1' in c['types'])
        zip_code = next(c['long_name'] for c in data['results'][0]['address_components'] if 'postal_code' in c['types'])
        county = next(c['long_name'] for c in data['results'][0]['address_components'] if 'administrative_area_level_2' in c['types'])

        # Print the results
        print('Street Address:', street_address)
        print('City:', city)
        print('State:', state)
        print('ZIP Code:', zip_code)
        print('County:', county)
        """

    def meals_sanitize(self, data, data_index):
        raise NotImplementedError

    def date_sanitize(self, data, data_index):
        """
        Standardize date formats to datetime.date(YYYY,M,D)
        Uncaught errors and dates before 2021 ask for user input correction
        """
        flag = False
        previous_date = None
        for item in data:
            dte = item[data_index]
            # Replace None with previous_date if applicable
            if dte is None:
                if previous_date is not None:
                    item[data_index] = previous_date
                else:
                    continue
            
            # Skip if value is not a string or datetime object
            if not isinstance(dte, str) and not isinstance(dte, dt):
                continue
                    
            # Try to parse the string into a datetime object
            if isinstance(dte, str):
                is_date = False
                for fmt in self.vars['convert']['to_date']:
                    try:
                        date_obj = dt.strptime(dte, fmt)
                        is_date = True
                        if fmt == "%Y-%m-%d":
                            date_obj = date_obj.date()
                        item[data_index] = date_obj
                        previous_date = date_obj
                        break
                    except ValueError:
                        pass
                if not is_date:
                    user_input = input(f'Found the string "{dte}" in date data, input a date in the following format MM/DD/YYYY, or press <ENTER> to delete : ')
                    if user_input == "":
                        data.remove(item)
                        print('    row removed from dataset')
                        flag = True
                        continue
                    for fmt in self.vars['convert']['to_date']:
                        try:
                            date_obj = dt.strptime(user_input, fmt)
                            is_date = True
                            if fmt == "%Y-%m-%d":
                                date_obj = date_obj.date()
                            item[data_index] = date_obj.date()
                            previous_date = date_obj.date()
                            break
                        except ValueError:
                            pass
                    if not is_date:
                        data.remove(item)
                        continue
            else:
                item[data_index] = dte.date()
                previous_date = dte.date()
            
            # Catch all datetime.datetime and convert to datetime.date
            if isinstance(item[data_index], datetime.datetime):
                item[data_index] = item[data_index].date()
                
            # Check if date is before 2021-01-01
            if item[data_index]< datetime.date(2021, 1, 1):
                user_input = input(f'The date "{item[data_index]}" is before 1/1/2021. Input a valid date in the following format MM/DD/YYYY, or press <ENTER> to delete : ')
                if user_input == "":

                    data.remove(item)
                    print('    row removed from dataset')
                    flag = True
                    continue
                is_date = False
                for fmt in self.vars['convert']['to_date']:
                    try:
                        date_obj = dt.strptime(user_input, fmt)
                        is_date = True
                        if fmt == "%Y-%m-%d":
                            date_obj = date_obj.date()
                        item[data_index] = date_obj.date()
                        previous_date = date_obj.date()
                        break
                    except ValueError:
                        pass
                if not is_date:
                    data.remove(item)
                    continue
        
        # If a row is deleted from the dataset, the next index will be skipped, this runs through the dataset again to make sure the skipped row is sanitized as well
        if flag:
            data = self.date_sanitize(data, data_index)

        return data

    def date_lbs_totals(self, key, data_index):
        print('\nDoing maths... ', end='')
        data = key['data']
        # Create a dictionary to store the totals for each date
        date_totals = {}
        for item in data:
            date = item[0]
            # Skip items with None or invalid date
            if date is None or not isinstance(date, datetime.date):
                continue
            # If date already exists in dictionary, add the weight to the total
            if date in date_totals:
                date_totals[date] += item[data_index]
            # Otherwise, add the date to the dictionary with the current weight
            else:
                date_totals[date] = item[data_index]
        # Calculate the total weight
        key['headers'].append(key['namekeyword'] + '_Sum')
        key['headers'].append(key['namekeyword'] + '_Percentage of total')
        total_weight = sum(date_totals.values())
        # Create a new list with the date, total weight, and percentage of total weight
        new_data = []
        for item in data:
            date = item[0]
            weight = item[data_index]
            # Skip items with None or invalid date
            if date is None or not isinstance(date, datetime.date):
                continue
            try:
                percentage = round(weight / date_totals[date], 2)
            except ZeroDivisionError:
                percentage = 1
            new_item = item + [round(date_totals[date], 2), percentage]
            new_data.append(new_item)
        # Sort the list by date
        new_data.sort()
        print('Done.')
        return new_data

    def create_dataset(self, datasets):
        """
        Take two datasets, do math and return a combined dataset.
        """
        match_index = self.vars['outfile']['match_index']
        dset1 = datasets[0]
        dset2 = datasets[1]

        # Create a list of all headers in datasets , initialize variables
        headers = [head for dset in datasets for head in self.vars[dset]['headers']]
        headers.insert(0, 'DATE')
        headers.append('APPROX SITE WEIGHT')
        datelist = []
        row1 = 0
        row2 = 0

        # Create a list of all dates in datasets for index 0 in final dataset
        while True:
            try:
                for set_index in range(len(datasets) - 1):
                    data1 = self.vars[dset1]['data'][row1][match_index]
                    data2 = self.vars[dset2]['data'][row2][match_index]
                    if data1 == data2:
                        datelist.append(data1)
                        row1 += 1
                        row2 += 1
                    elif data1 < data2:
                        datelist.append(data1)
                        row1 += 1
                    elif data1 > data2:
                        datelist.append(data2)  
                        row2 += 1
            except IndexError:
                break

        # Create the final dataset
        dataset = []
        row1 = 0
        row2 = 0
        for dte in datelist: 
            drow= [dte]
            date1 = self.vars[dset1]['data'][row1][match_index]
            date2 = self.vars[dset2]['data'][row2][match_index]
            fill_index = None
            if date1 != date2:
                if date1 == dte:

                    # Fill in the data after the DATE with all of the data from dset1 data
                    datarow = self.vars[dset1]['data'][row1]
                    for d in datarow:
                        drow.append(d)
                    drow.append(dte)

                    # Check dset2 fill_index to see if data needs to be filled for final weight calculations
                    if not self.vars[dset2]['data_index']['fill_col'] == "None":
                        fill_index = self.vars[dset2]['data_index']['fill_col']
                        try:
                            previous_data2 = self.vars[dset2]['data'][row2-1][fill_index]
                        except IndexError:
                            previous_data2 = 0
                
                    # Fill in 0 in all data cols if none exists for that date, except in the case fill_index = True
                    for i in range(1, len(datarow)):
                        if fill_index and i == fill_index:
                            drow.append(previous_data2)
                        else:
                            drow.append(0)                    
                    
                    row1 += 1

                elif date2 == dte:
                    # Fill DATE in index 0
                    datarow = self.vars[dset2]['data'][row2]
                    drow.append(dte)

                    # Check dset1 fill_index to see if data needs to be filled for final weight calculations
                    if not self.vars[dset1]['data_index']['fill_col'] == "None":
                        fill_index = self.vars[dset1]['data_index']['fill_col']
                        try:
                            previous_data1 = self.vars[dset1]['data'][row1-1][fill_index]
                        except IndexError:
                            previous_data1 = 0

                    # Fill in 0 in all data cols if none exists for that date, except in the case fill_index = True
                    for i in range(1, len(datarow)):
                        if fill_index and i == fill_index:
                            drow.appen(previous_data1)             
                        else:
                            drow.append(0)
                        
                    # Fill in the rest of the datarow with the dset2 data
                    for d in datarow:
                        drow.append(d)
                    row2 += 1

            elif date1 == date2:
                if date1 == dte:
                    for d in self.vars[dset1]['data'][row1]:
                        drow.append(d)
                    for d in self.vars[dset2]['data'][row2]:
                        drow.append(d)
                    row1 += 1
                    row2 += 1
            
            # Do math for the total at the final index
            # 032523 Percentage of total est. weight for the day at each location
            # x Total weight from dump receipts
            # output APPROX WEIGHT at each site based on receipts and not user guesses
            percentage = self.vars[dset1]['data_index']['percentage'] + 1
            try:
                total = self.vars[dset2]['data_index']['total'] + len(self.vars[dset1]['data'][row1]) + 1
            except IndexError:
                continue

            drow.append(drow[percentage] * drow[total])
            dataset.append(drow)
        
        self.dataset['headers'] = headers
        self.dataset['data'] = dataset
        return

    def parse_addresses(self, dataset, data_index):
        print('\nCleaning up addresses... ', end='')
        # TODO Google Address Validation has all of this data in it. Rework code to incorporate this
        # TODO GAV also can return partial matches, perhaps user corrction prompt could include this as an option
        headers = ['CITY', 'STATE', 'ZIP']
        for head in headers:
            dataset['headers'].append(head)
        state_abbreviations = {'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
                            'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
                            'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
                            'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
                            'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
                            'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
                            'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
                            'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
                            'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
                            'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
                            'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
                            'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
                                    'Wisconsin': 'WI', 'Wyoming': 'WY'}
        for item in dataset['data']:
            try:
                # TODO Spagett use the GAV to get this
                address = item[data_index]
                if address == 0:
                    for i in range(3):
                        item.append(0)
                    continue
                city = address.split(', ')[1]
                statezip = address.split(', ')[2]
                if ' ' in city: # in the case that no address, only city and statezip were given
                    statezip = city
                    city = address.split(', ')[0]
                    # TODO this will mess things up if there is a multi-word city like Las Vegas

                if ' ' in statezip:
                    state = statezip.split(' ')[0]        
                    zip_code = statezip.split(' ')[1]                
                else:
                    state = statezip                          
                    zip_code = 0
               
                if state in state_abbreviations:
                    state = state_abbreviations[state]
                
                item.append(city)
                item.append(state)
                item.append(zip_code)
            except IndexError:
                continue

        print('Done.')
        return dataset
    
    def write_csv(self, headers, dataset, openfile=False):
        """Write the dataset to a csv file"""
        now = dt.now()
        timestamp = now.strftime('%m%d%Y_%H%M%S')
        filename = self.vars['outfile']['namekeyword'] + '_' + str(timestamp) + self.vars['outfile']['type']
        outpath = self.vars['outfile']['path']
        print(f'{outpath=}  {filename=}')
        with open(outpath + filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(dataset)

        if openfile:
            os.startfile(outpath + filename)


class Report():
    # TODO Report options are in variables.json, might be good to put it in here at some point
    def __init__(self, dataset, params):
        self.dataset = dataset
        self.params = params
        chart_title = self.params['title']
        if self.params['date_range'] != 'all':
            self.dataset['data'] = self.filter_data_by_date(self.dataset, self.params['date_range'])
            chart_title += '\n\n' + self.params['date_range'][0] + ' to ' + self.params['date_range'][1]
        chart_type = self.params['chart_type']
        self.df = pd.DataFrame(self.dataset['data'], columns=self.dataset['headers'])

        # Convert the 'sum_data' column items to a numerical data type
        self.df[self.params['sum_data']] = pd.to_numeric(self.df[self.params['sum_data']], errors='coerce')

        # Group the data by the 'group_data' column and calculate the sum of 'APPROX SITE WEIGHT'
        grouped = self.df.groupby(self.params['group_data'])[self.params['sum_data']].sum()
        grouped = grouped[grouped != 0]

        # Calculate the total sum and percentages
        total_sum = grouped.sum()
        percentages = grouped / total_sum * 100
        sums = grouped

        # Define a custom autopct function that returns the percentage and the sum
        def my_autopct(pct):
            sum_value = int(round(pct/100 * total_sum))
            if pct < 5:
                return ''
            else:
                # TODO This should display the name of the item above the percentage on the chart. Currently does nothing
                name_list = [name for name in grouped.index]
                #print(f'{name_list=}')
                name = ''
                if len(name_list) > 0:
                    name = '' # temp
                return f'{name}\n{pct:.1f}%\n({sum_value:,}lbs)'

        # Create a pie chart with a legend to the side
        labels = [f'{name}' if percentages.loc[name] >= 5 else '' for name in grouped.index]
        fig, ax = plt.subplots(figsize=(10,10))
        wedges, texts, autotexts = ax.pie(grouped, labels=labels, autopct=my_autopct, startangle=90)
        legend_items = [f"{name} ({percentages.loc[name]:.1f}% - {sums.loc[name]:,}lbs)" for name in grouped.index]
        ax.legend(wedges, legend_items, title=self.params['group_data'], loc='center left', bbox_to_anchor=(1, 0.5), fancybox=True, shadow=True)
        plt.setp(texts, size=10, weight='bold')
        
        # TODO Make this handle extra parameters for each type of chart
        #else:
        #    grouped.plot(kind=chart_type)        
        plt.title(chart_title)
        plt.show()
    
    def filter_data_by_date(self, dataset, date_filter, col_index=0):
        """Filter a dataset by date range
        Takes two string dates MM/DD/YYYY in a list
        col_index is where to find the dates
        """
        filtered_data = []
        dates = []
        date_format = '%m/%d/%Y'
        for date in date_filter:
            dates.append(dt.strptime(date, date_format).date())
        for row in dataset['data']:
            check_date = dt.strptime(row[col_index], date_format).date()
            if check_date >= dates[0] and check_date <= dates[1]:
                filtered_data.append(row)
        return filtered_data

def highlight_options(options, stdscr, title=None):
    # Turn off cursor blinking
    curses.curs_set(0)

    # Define options
    option_index = 0

    while True:
        # Clear screen
        stdscr.clear()
        stdscr.keypad(True)
        
        # Display title
        if title:
            stdscr.addstr(0, 0, title, curses.A_BOLD)
            stdscr.addstr(1, 0, "-" * len(title))

        # Display options
        for i, option in enumerate(options):
            if i == option_index:
                # Highlight the selected option
                stdscr.addstr(i+2, 0, option, curses.A_REVERSE)
            else:
                stdscr.addstr(i+2, 0, option)

        # Get user input
        key = stdscr.getch()
        
        # Handle user input
        if key == curses.KEY_UP or key == 450:
            option_index = (option_index - 1) % len(options)
        elif key == curses.KEY_DOWN or key == 456:
            option_index = (option_index + 1) % len(options)
        elif key == curses.KEY_ENTER or key in [10, 13]:
            # User selected an option
            return option_index


if __name__ == '__main__':
    Beautification_Stats('variables.json')
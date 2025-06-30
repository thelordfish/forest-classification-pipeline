
"""
findwhereleftoff_drive_api.py

Author: Oliver Appleby

Description:
This script uses the Google Drive API to check which chunked satellite plot exports
have completed successfully, and which are missing, within Google Drive without having to download the results and run anything locally.
It does this based on subfolders named by country and year. 
It prints a summary of missing ranges in dictionary format to allow easier re-submission into PlotToSat.

Usage:
    Adjust the CONFIGURATION section at the top of the file to match your Drive structure.
    Then simply run:

    python findwhereleftoff_drive_api.py


Dependencies:
    google-auth, google-api-python-client, google-auth-oauthlib, pandas

Notes:
    You must have a valid Google OAuth credentials JSON file, and grant read-only access
    to your Drive. Adjust the folder names to match your Google Drive structure.
    - Do not commit your OAuth JSON file to public GitHub repositories.

"""



import re
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


##===================##
###~ CONFIGURATION ~###
##===================##

# these are changed by editing this section directly

DEFAULT_COUNTRIES = ["Finland", "Sweden", "Norway"]
DEFAULT_YEARS = list(range(2015, 2023))
DEFAULT_TOTAL_PLOTS = {
    "Finland": 2172,
    "Sweden": 10017,
    "Norway": 26,
}

DEFAULT_PARENT_FOLDER_NAME = None  # e.g. "MyFolder" to scan a specific Drive folder, or None for root
DEFAULT_SEARCH_IN_ROOT = True
DEFAULT_CREDENTIALS_FILE = "drive_credentials.json"




class PlotExportChecker:
    """
    This class checks what plot chunks have been exported to Google Drive
    and reports which parts of each country/year combination are finished or still missing.
    """

    def __init__(
    self,
    drive_credentials_file=DEFAULT_CREDENTIALS_FILE,
    parent_folder_name=DEFAULT_PARENT_FOLDER_NAME,
    search_in_root=DEFAULT_SEARCH_IN_ROOT,
    countries=DEFAULT_COUNTRIES,
    years=DEFAULT_YEARS,
    total_plots=DEFAULT_TOTAL_PLOTS
    ):
        """
        Initialize the PlotExportChecker with configurable parameters.
        """
        self.drive_credentials_file = drive_credentials_file
        self.parent_folder_name = parent_folder_name
        self.search_in_root = search_in_root
        self.countries = countries
        self.years = years
        self.total_plots = total_plots

        # internal initial state
        self.drive_service = None
        self.parent_folder_id = None
        self.country_year_folders = {}
        self.unfinished_exports = {}



    def authenticate_google_drive(self):

        """
        Start the Google OAuth login and create a drive_service object
        so we can talk to Google Drive.
        """

        scopes = ['https://www.googleapis.com/auth/drive.metadata.readonly']
        flow = InstalledAppFlow.from_client_secrets_file(self.drive_credentials_file, scopes)
        credentials = flow.run_local_server(port=0)
        self.drive_service = build('drive', 'v3', credentials=credentials)

    def pick_parent_folder(self):

        """
        Figure out which folder to search inside, either
        the root folder or a user-specified folder name.
        """

        if self.search_in_root:
            self.parent_folder_id = "root"
            print("Searching in the ROOT of your Google Drive.")
        else:
            response = self.drive_service.files().list(
                q=f"name='{self.parent_folder_name}' and mimeType='application/vnd.google-apps.folder'",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            folders = response.get('files', [])
            if not folders:
                raise FileNotFoundError(f"Could not find folder named: {self.parent_folder_name}")
            self.parent_folder_id = folders[0]['id']
            print(f"Found folder '{self.parent_folder_name}' with ID {self.parent_folder_id}")

    def list_country_year_folders(self):

        """
        Get all the country/year subfolders inside the parent folder.
        For example:
          Greenbelts_S2_Finland_2016
        """
        response = self.drive_service.files().list(
            q=f"'{self.parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'",
            fields='files(id, name)'
        ).execute()

        for folder in response.get('files', []):
            self.country_year_folders[folder['name']] = folder['id']

    @staticmethod
    def is_csv_file(filename):

        """
        Checks if a file looks like a CSV file by its name.
        """

        return filename.lower().endswith(".csv")

    @staticmethod
    def extract_chunk_end_index(filename):

        """
        Given a filename with chunk markers, like
          feature_vectors_S2_0000000000_0000000500_S2_mean.csv
        extract the second number (the chunk end).
        """

        match = re.search(r"_(\d+)_(\d+)_S\d+_mean\.csv$", filename)
        if match:
            return int(match.group(2))
        else:
            return -1

    def check_country_year_completion(self):

        """
        Check each country and year to see how many plots have finished,
        and collect any unfinished ranges.
        """

        print("\n*****************************")
        print("COMPLETION REPORT")
        print("*****************************\n")

        for country in self.countries:
            for year in self.years:
                folder_name = f"Greenbelts_S2_{country}_{year}"
                folder_id = self.country_year_folders.get(folder_name)
                total_plots_for_country = self.total_plots[country]

                if folder_id is None:
                    print(f"{country} {year}: folder missing, assuming 0 of {total_plots_for_country} done")
                    self.unfinished_exports[(country, year)] = (0, total_plots_for_country)
                    continue

                # list CSVs in the folder
                response = self.drive_service.files().list(
                    q=f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder'",
                    fields="files(name)"
                ).execute()
                csv_files = [f['name'] for f in response.get('files', []) if self.is_csv_file(f['name'])]

                # find highest chunk
                if csv_files:
                    max_end_index = max(
                        self.extract_chunk_end_index(name)
                        for name in csv_files
                    )
                else:
                    max_end_index = -1

                completed = max_end_index + 1
                remaining = total_plots_for_country - completed

                print(f"{country} {year}: {completed} of {total_plots_for_country} done "
                      f"({remaining} left to do)")

                if completed < total_plots_for_country:
                    self.unfinished_exports[(country, year)] = (completed, total_plots_for_country)

    def print_export_ranges(self):

        """
        Show the export ranges in the correct dictionary syntax.
        """

        print("\n*** AUTO-GENERATED EXPORT RANGES FOR UNFINISHED PLOT RANGES ONLY ***")
        print("export_ranges = {")
        for (country, year), (start, end) in self.unfinished_exports.items():
            print(f"    ('{country}', {year}): ({start}, {end}),")
        print("}")

    def run(self):

        """
        Orchestrates the whole process from start to finish.
        """

        self.authenticate_google_drive()
        self.pick_parent_folder()
        self.list_country_year_folders()
        self.check_country_year_completion()
        self.print_export_ranges()


if __name__ == "__main__":
    checker = PlotExportChecker(
        drive_credentials_file=DEFAULT_CREDENTIALS_FILE,
        parent_folder_name=DEFAULT_PARENT_FOLDER_NAME,
        search_in_root=DEFAULT_SEARCH_IN_ROOT
    )
    checker.run()


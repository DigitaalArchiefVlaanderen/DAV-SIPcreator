Shield: [![CC BY 4.0][cc-by-shield]][cc-by]

This work is licensed under a
[Creative Commons Attribution 4.0 International License][cc-by].

[![CC BY 4.0][cc-by-image]][cc-by]

[cc-by]: http://creativecommons.org/licenses/by/4.0/
[cc-by-image]: https://i.creativecommons.org/l/by/4.0/88x31.png
[cc-by-shield]: https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg

# SIPCreator

SIPCreator assists the user in creating SIPs that follow a specific rule-set.
It does this by allowing the user to select which documents to add, and generating a grid based on this input.
The user can then add metadata in this grid related to their documents.

Once all relevant information is filled in, and all rules are followed, a SIP can be created.

This project is set up with the Vlaamse Overheid as a focus.
It focusses on SIPs based on Series, as well as uploading to a Digitaal Archief.

## Current Features

- Adding folders containing documents (recursively)
- Selection of Series through the Serieregister API (authorization required)
- Entering metadata in a grid
- Rule checking in grid
- Uploading SIPs to Edepot over FTPS (authorization required)
- Upload status check

## Coming up

- Reloading folder structure once grid has been generated (currently once the grid is generated, local changes are irrelevant)
- Checking status of upload per document rather than for the whole SIP

## Installation

Download the Windows installer (Work In Progress) or build te project yourself.

### Build the project

To build the project yourself, you are going to need [Python 3.11+](https://www.python.org/downloads/) installed on your system.
Once you have Python installed, follow the following steps.

#### Windows

Open cmd and go to the folder containing the project, then enter the following commands.
IF you do not want an exe to be created, you only need to do steps 1-3.

1. `python -m venv venv`
2. `venv\Scripts\activate.bat`
3. `pip install -r requirements.txt`
4. `pip install -r requirements.build.txt`
5. `pyinstaller --noconfirm --onefile --windowed main.py`

If you chose to create the exe, a folders will now be created in the project directory, `dist`.
Your exe can be found in this folder.

If you chose not to create an exe, you can run the project using the following command.
`python main.py`

Every time you are running the project in the future, you will need to repeat steps 2 and 3 before running the command above.

#### Linux

WIP

#### Mac

WIP

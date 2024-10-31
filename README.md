# supersed
<img src="https://github.com/user-attachments/assets/630809b4-369b-4e88-8f92-5f926aff72b6" width="300" />

**supersed** is a natural language-powered file editor that leverages LLMs to perform various file manipulations on txt or txt-like files based on user instructions. Simplify your workflow by managing and editing your text files using plain English commands. No more googling for the right commands!

## Features

- **Natural Language Editing:** Modify text files using simple English commands.
- **Backup and Restore:** Automatically backup files before making changes and restore them if needed.
- **Flexible File Targeting:** Specify individual files or use patterns to target multiple files, including those in subdirectories.
- **Cross-Platform Compatibility:** Works seamlessly on both Linux and macOS systems.

## Installation

1. **Clone the Repository:**
   ```
   bash
   git clone https://github.com/akcanuv/supersed.git
   cd supersed
   ```

2.	**Install Dependencies:**
Ensure you have Python 3 installed. Then, install the required Python packages:

    ```
  	pip install openai
    ```


4.	**Set Up OpenAI API Key:**
Obtain your OpenAI API key from OpenAI and set it as an environment variable:
- Linux/macOS:
```export OPENAI_API_KEY='your-api-key-here'```
- Windows (Command Prompt):
```set OPENAI_API_KEY=your-api-key-here```
- Windows (PowerShell):
```$env:OPENAI_API_KEY="your-api-key-here"```

## Usage

Make the script executable (if not already):

```
chmod +x supersed.py
```

Run the script with your desired command:

```
./supersed.py "your instruction here" -f [file_patterns]
```

### Examples

1. Update the README.md by Reviewing supersed.py:

```
./supersed.py "update the readme file by reviewing the code in supersed.py" -f README.md
```


2. Remove All Blank Spaces in Text Files Within test_files Directory:

```
./supersed.py "remove all the blank spaces in the text files in test_files directory" -f "test_files/**/*.txt"
```


3. Save Current File Versions to Backup:

```
./supersed.py save -f "*.txt"
```


4. Restore Files from Backup:

```
./supersed.py restore
```



## Commands

- Execute a Command:
Provide an instruction and specify target files using -f:

```
./supersed.py "your instruction" -f "file_pattern"
```


- Save Backup:
Backup specified files:

```
./supersed.py save -f "file_pattern"
```


- Restore Backup:
Restore all backed-up files:

```
./supersed.py restore
```



## Backup and Restore

- Backup: Before executing any changes, supersed automatically backs up the target files to a .backup directory. To manually update the backup, use the save command.
- Restore: If you need to revert changes, use the restore command to retrieve the original files from the .backup directory.

## Notes

- File Patterns: Use glob patterns to specify target files. For recursive searches, use patterns like **/*.txt.
- Safety: Always ensure you have backups of important files. Use the save command to create a new backup point after satisfactory changes.

## License

This project is licensed under the MIT License.

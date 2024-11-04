# supersed
<img src="https://github.com/user-attachments/assets/630809b4-369b-4e88-8f92-5f926aff72b6" width="300" />

**supersed** is a natural language-powered file editor that leverages LLMs to perform various file manipulations on txt or txt-like files based on user instructions. Simplify your workflow by managing and editing your text files using plain English commands. No more googling for the right commands!

## Features

- **Natural Language Editing:** Modify text files using simple English commands.
- **Backup and Restore:** Automatically backup files before making changes and restore them if needed.
- **Flexible File Targeting:** Specify individual files or use patterns to target multiple files, including those in subdirectories.
- **Cross-Platform Compatibility:** Works seamlessly on both Linux and macOS systems.

## Installation

1. **Use PyPI package:**
If you simply want to use `supersed`, install it from PyPI using.

   ```
   pip install supersed
   ```
2. **Clone the Repository:**
If you would like to contribute to `supersed`, consider cloning the github directory.

   ```
   git clone https://github.com/akcanuv/supersed.git
   cd supersed
   pip install -e .
   ```
3.	**Set Up OpenAI API Key:**
Obtain your [OpenAI API Key](https://platform.openai.com/api-keys) from OpenAI and set it as an environment variable:
- Linux/macOS:
```export OPENAI_API_KEY='your-api-key-here'```
- Windows (Command Prompt):
```set OPENAI_API_KEY=your-api-key-here```
- Windows (PowerShell):
```$env:OPENAI_API_KEY="your-api-key-here"```
Note that running the above command sets the API key as environment variables only temporarily. To set it permanently, add the statement to `.bashrc`, `.zshrc` or any other shell config file for the shell you're using.

## Usage

Run the script with your desired command:

```
supersed "your instruction here"
```

## Commands

- Execute a Command:
Provide an instruction and specify the scope of the commands with -s, default scope is `.`:

```
supersed "your instruction" -s "scope"
```


- Save Backup:
Backup specified files:

```
supersed save
```


- Restore Backup:
Restore all backed-up files:

```
supersed restore
```

### Examples

1. Update the README.md by Reviewing supersed.py:

```
supersed "update the README.md file by reviewing the code in supersed.py"
```


2. Remove All Blank Spaces in Text Files Within test_files Directory:

```
supersed "remove all the blank spaces in the text files in test_files directory"
```


3. Save Current File Versions to Backup:

```
supersed save
```


4. Restore Files from Backup:

```
supersed restore
```

## Backup and Restore

- Backup: Before executing any changes, supersed automatically backs up the target files to a .backup directory. To manually update the backup, use the save command.
- Restore: If you need to revert changes, use the restore command to retrieve the original files from the .backup directory.

## Notes

- File Patterns: Use glob patterns to specify target files. For recursive searches, use patterns like **/*.txt.
- Safety: Always ensure you have backups of important files. Use the save command to create a new backup point after satisfactory changes.

## License

This project is licensed under the MIT License.

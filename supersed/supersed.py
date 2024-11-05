#!/usr/bin/env python3

import os
import sys
import shutil
import argparse
import subprocess
import glob
import re
import platform  
from fnmatch import fnmatch
from typing import List

# Import OpenAI client
from openai import OpenAI

# Create the OpenAI client instance
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

if not client.api_key:
    print("Error: OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    sys.exit(1)

# Save the list of modified files to .modified_files.ss
def update_modified_files(files):
    modified_file_path = os.path.join('.backup', '.modified_files.ss')
    with open(modified_file_path, 'w') as f:
        for file in files:
            f.write(file + '\n')

# Backup files with option to force re-backup
def backup_files(files, force=False):
    backup_dir = os.path.join(os.getcwd(), '.backup')
    os.makedirs(backup_dir, exist_ok=True)
    
    for file in files:
        backup_path = os.path.join(backup_dir, file)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy(file, backup_path)
    
    print("Backup created.")
    update_modified_files(files)

# Automatic backup on initial run
def automatic_backup(files):
    backup_dir = os.path.join(os.getcwd(), '.backup')
    os.makedirs(backup_dir, exist_ok=True)
    for file in files:
        backup_path = os.path.join(backup_dir, file)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy(file, backup_path)
    print("Automatic backup created.")

# Update the list of modified files in .modified_files.ss
def update_modified_files(files):
    modified_file_path = os.path.join('.backup', '.modified_files.ss')
    with open(modified_file_path, 'w') as f:
        for file in files:
            f.write(file + '\n')

# Save only recent changes or all files in scope if specified
def save_backup(files, scope=None):
    backup_dir = os.path.join(os.getcwd(), '.backup')
    os.makedirs(backup_dir, exist_ok=True)
    for file in files:
        backup_path = os.path.join(backup_dir, file)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy(file, backup_path)
    
    if scope is None:
        print("Backup updated with current file versions (recent changes only).")
    else:
        print("Backup updated with current file versions (all files in scope).")
    
    update_modified_files(files)

# Restore recent changes or all files in scope if specified
def restore_files(scope=None):
    backup_dir = os.path.join(os.getcwd(), '.backup')
    modified_file_path = os.path.join(backup_dir, '.modified_files.ss')
    
    if not os.path.exists(backup_dir):
        print("\nNo backup found to restore.")
        return
    
    files_to_restore = []
    if scope:
        # Restore all files within the specified scope
        files_to_restore = [os.path.relpath(os.path.join(root, file), backup_dir) 
                            for root, _, files in os.walk(backup_dir) 
                            for file in files]
    else:
        # Only restore files listed in .modified_files.ss
        if os.path.exists(modified_file_path):
            with open(modified_file_path, 'r') as f:
                files_to_restore = [line.strip() for line in f.readlines()]
    
    # Restore files
    for file in files_to_restore:
        backup_file = os.path.join(backup_dir, file)
        os.makedirs(os.path.dirname(file), exist_ok=True)
        shutil.copy(backup_file, file)
    
    print("\nFiles restored from backup.")
    update_modified_files(files_to_restore)

def extract_filenames_from_text(text):
    # Improved regex to find filenames with paths (e.g., test_files/file1.txt)
    pattern = r'[\w./-]+\.\w+'
    return re.findall(pattern, text)

def read_file_contents(filenames):
    contents = {}
    for filename in filenames:
        if os.path.isfile(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                contents[filename] = f.read()
    return contents

def get_instructions_and_files(prompt, scope):
    try:
        
        # System message for instructing the assistant
        system_prompt = (
            "You are supersed, a tool that analyzes user instructions and determines the steps needed to accomplish the task.\n"
            "Under a section called 'Plan', provide a numbered list of steps to accomplish the task.\n"
            "Under a section called 'Files to Modify/Create', provide an appropriate command using the scope that will display the relevant files needed to be modified or created when parsed, use `find`. When specifically asked to create a file, use `touch`. When specifically asked to update a file, use `find`.\n" 
            "Under a section called 'Context Files', provide an appropriate command using the scope that will display the relevant files needed to be read for context when parsed, use `find`. Files that are to be updated must also be included in the context.\n" 
            "Under a section called 'Execution Table' provide a single step or a sequence of steps to be executed sequentially either with a `COMMAND: ` or an `LLM: ` prefix.  You may chain any number or order of COMMAND: and LLM: as appropriate as per Plan. To complete the task.\n"
            "The 'COMMAND: ' prefix should be followed by the command to run using a CLI tool. The COMMAND statements may include creation, deletion, copying, moving, executing and in-place modification of files within the given scope.\n"
            "Example 1: 'COMMAND: sed -i '' '/^$/d; s/^[QA]: //' test/example_1.txt\n"
            "The 'LLM: ' prefix should be followed by a generated prompt which is <instruction> to modify the required files. The instructions, files_to_modify, context_files must be clearly seperated using <tags> followed by '{}'. The tags will be used to parse the message to be sent to the model. They should be in a readable format such as: 'LLM 'Carry out the <instruction>{instruction} to modify the contents of <files_to_modify>{files_to_modify} using information in <context_files>{context_files}.''\n" 
            "Example 2: 'LLM: <instruction>{'Extract the details of the project from README.md and the dependencies from requirements.txt and populate the fields in pyproject.toml'} of <files_to_modify>{'./pyproject.toml'} using information in <context_files>{'./pyproject.toml', './README.md', './requirements.txt'}.'\n" 
            "Example 3: 'LLM: For each file in <context_files>{'001.txt', '002.txt', '003.txt',...}, run <instruction>{'Correct the grammatical errors in the provided text and provide just the updated test. Do not include any additional explanation.'} and replace the contexts in <files_to_modify>{'001.txt', '002.txt', '003.txt',...}.\n"
            "When processing more than one file with LLM, modify the <instruction> assuming it is only acting on one file at a time, so it should not reference any files in <instruction>.\n"
            "<context_files> and <files_to_modify> may be a `find` command for user instructions such as a file pattern or when 'all files' is mentioned, do not include quotes inside {'find ... '} when using the command, rather directly put the command in {} like {find ...}" 
            "Provide clearly all the sections sections for 'Plan', 'Files to Modify/Create', 'Context Files' and 'Execution Table', even if there are no Files to Create/Modify and Context Files (default to None).\n"
            "DO NOT enclose any section with backticks like ```bash $cmd```.\n" 
            "DO NOT include files in .backup in 'Files to Modify/Create' or 'Context Files'\n when executing find use ! -path '*.backup*'"
            "DO NOT number the Execution Table.\n"
            "DO NOT include any additional explanation."
        )
        
        # User message with prompt and scope of execution
        user_prompt = (
            f"Instruction: {prompt}\n\n"
            f"Scope: {scope}\n"
            "Scope determines the extent to which supersed has file access, it may be a file or a directory, or pattern, Default scope is '.' - the entire file tree of current working directory.\n"
            "Provide clear sections for 'Plan', 'Files to Modify', 'Context Files' and 'Execution Table'.\n" 
            "Do not include any additional explanation."
        )

        # Call to OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )
        plan = response.choices[0].message.content.strip()
        return plan
    except Exception as e:
        print(f"Error getting instructions from LLM: {e}")
        sys.exit(1)

def extract_filenames_from_text(line):
    # Extracts filenames from a line of text by searching for patterns like file paths
    return re.findall(r'[./\w-]+(?:\.\w+)?', line)

def parse_plan(plan):
    # Initialize lists for sections
    files_to_modify = []
    context_files = []
    instructions = ""
    execution_table = ""
    current_section = None

    # Split the plan into lines
    lines = plan.split('\n')
    for line in lines:
        line = line.strip()

        # Detect sections
        if line.lower() == 'plan:':
            current_section = 'plan'
            continue
        elif line.lower() == 'files to modify:' or line.lower().startswith('files to modify'):
            current_section = 'modify'
            continue
        elif line.lower() == 'context files:' or line.lower().startswith('context files'):
            current_section = 'context'
            continue
        elif line.lower() == 'execution table:' or line.lower().startswith('execution table'):
            current_section = 'execute'
            continue
        # Add content based on section
        if current_section == 'plan':
            instructions += line + "\n"
        elif current_section == 'modify':
            # Handle cases where Files to Modify is explicitly marked as empty
            if line.lower() == '- none':
                continue
            extracted_files = execute_find_command(line) if line else []
            files_to_modify.extend(extracted_files)
        elif current_section == 'context':
            # Handle cases where Context Files is explicitly marked as empty
            if line.lower() == '- none':
                continue
            extracted_files = execute_find_command(line) if line else []
            context_files.extend(extracted_files)
        elif current_section == 'execute':
            execution_table += line + "\n"
    # Return parsed elements, ensure deduplication and clean formatting
    return list(set(files_to_modify)), list(set(context_files)), instructions.strip(), execution_table.strip()

def execute_find_command(command_line: str) -> List[str]:
    """
    Executes one or more 'find' and 'touch' commands extracted from the command_line string
    and returns a list of matching or created file paths.

    Args:
        command_line (str): The input string containing the 'find' and/or 'touch' command(s).

    Returns:
        List[str]: A list of file paths returned by the 'find' command(s) and created by 'touch' command(s).
    """
    if command_line.startswith('None'):
        return []
    
    try:
        # Only proceed if command_line is valid and contains 'find' or 'touch'
        if not command_line or ("find" not in command_line and "touch" not in command_line):
            print(f"Skipping invalid command: {command_line}")
            return []
        
        # Initialize a list to collect all found and created files
        all_files = []

        # Split the command_line into individual commands based on separators ';', '|', '&', or newlines
        # This allows handling multiple commands in a single command_line string
        commands = re.split(r'[;&|]', command_line)

        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue  # Skip empty commands

            # Remove leading numbering or labels (e.g., '1. ', '2) ', etc.)
            # This regex removes any leading digits, followed by a dot or parenthesis and optional space
            cmd = re.sub(r'^\d+[\.\)]\s*', '', cmd)

            if not cmd:
                continue  # Skip if command is empty after stripping

            # Check if the command is a 'find' command
            if cmd.lower().startswith('find'):
                try:
                    # Execute the 'find' command and capture the output
                    result = subprocess.run(
                        cmd,
                        shell=True,               # Execute through the shell
                        text=True,                # Capture output as text
                        capture_output=True,      # Capture stdout and stderr
                        check=True                # Raise CalledProcessError on non-zero exit
                    )
                    
                    # Split the output by lines to get individual file paths
                    files = result.stdout.strip().split('\n')
                    
                    # Filter out any empty strings and extend to the all_files list
                    valid_files = [file for file in files if file]
                    all_files.extend(valid_files)
                
                except subprocess.CalledProcessError as e:
                    print(f"Error executing 'find' command: {cmd}")
                    print(f"Error message: {e.stderr.strip()}")
                    continue  # Skip to the next command
                
            # Check if the command is a 'touch' command
            elif cmd.lower().startswith('touch'):
                try:
                    # Extract the file paths from the 'touch' command
                    # Use shlex.split to handle file paths with spaces and quotes
                    import shlex
                    touch_parts = shlex.split(cmd)
                    
                    # Remove 'touch' from the parts to get the file paths
                    file_paths = touch_parts[1:]
                    
                    if not file_paths:
                        print(f"No file paths specified in 'touch' command: {cmd}")
                        continue  # Skip if no files are specified
                    
                    # Execute the 'touch' command to create the files
                    subprocess.run(
                        cmd,
                        shell=True,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    
                    # Add the created file paths to the all_files list
                    all_files.extend(file_paths)
                
                except subprocess.CalledProcessError as e:
                    print(f"Error executing 'touch' command: {cmd}")
                    print(f"Error message: {e.stderr.strip()}")
                    continue  # Skip to the next command
                except ValueError as ve:
                    print(f"Error parsing 'touch' command: {cmd}")
                    print(f"Error message: {str(ve)}")
                    continue  # Skip to the next command
            
            else:
                # If the command is neither 'find' nor 'touch', skip it
                print(f"Unsupported command skipped: {cmd}")
                continue
        
        return all_files

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return []

def strip_outer_quotes(text):
    # Check if the string starts and ends with the same quote character (either " or ')
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]  # Remove only the outermost quotes
    return text  # Return as-is if no matching outer quote

def process_llm_instruction(command, context_contents):
    # Extract the main instruction, files to modify, and context files
    instruction_match = re.search(r"<instruction>\{(.+?)\}", command)
    files_to_modify_match = re.search(r"<files_to_modify>\{(.+?)\}", command)
    context_files_match = re.search(r"<context_files>\{(.+?)\}", command)

    # Get the instruction text
    instruction = instruction_match.group(1) if instruction_match else ""

    # Process files to modify, handling both direct lists and `find` commands
    if files_to_modify_match:
        files_to_modify_content = strip_outer_quotes(files_to_modify_match.group(1).strip())
        if files_to_modify_content.startswith("find "):
            # Execute find command to get list of files
            files_to_modify = execute_find_command(files_to_modify_content)
        else:
            # Parse files as a comma-separated list
            files_to_modify = [file.strip().strip("'\"") for file in files_to_modify_content.split(",")]
    else:
        files_to_modify = []

    # Process context files, handling both direct lists and `find` commands
    if context_files_match:
        context_files_content = strip_outer_quotes(context_files_match.group(1).strip())
        if context_files_content.startswith("find "):
            # Execute find command to get list of files
            context_files = execute_find_command(context_files_content)
        else:
            # Parse files as a comma-separated list
            context_files = [file.strip().strip("'\"") for file in context_files_content.split(",")]
    else:
        context_files = []
    
    # Execute LLM calls for each file to modify
    for file in files_to_modify:
        if os.path.isfile(file):
            # Read the content of the file to modify
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Gather context contents based on specified context files
            context_data = {cf: context_contents.get(cf, "") for cf in context_files}

            # Call the LLM with the parsed instruction, content, and context
            edited_content = process_with_llm(instruction, content, context_data)
            
            # Write the modified content back to the file
            with open(file, 'w', encoding='utf-8') as f:
                f.write(edited_content)
            print(f"Processed file with LLM: {file}")
        else:
            print(f"File not found: {file}")

def process_with_llm(prompt, content, context_contents):
    try:
        # Assemble the main prompt with the instruction
        full_prompt = (
            f"Follow the instruction below, read the context files, and apply the user's instruction to the provided content. "
            f"Return only the modified content without additional explanations.\n\n"
            f"{prompt}\n\n"
        )

        # Append each context file's content with a heading
        for context_filename, file_content in context_contents.items():
            full_prompt += f"### Content of {context_filename}\n{file_content}\n"

        # Add the content to modify at the end with a clear heading
        full_prompt += f"\n### Content to Modify\n{content}\n"

        # Call the LLM API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": (
                    "You are a helpful assistant that edits text files based on user instructions."
                    " Apply the user's instruction to the provided content and return only the modified content without additional explanations."
                )},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0
        )

        # Return the modified content
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error processing with LLM: {e}")
        return content  # Return original content if there's an error

def get_target_files(file_patterns):
    if file_patterns:
        # If specific file patterns are provided, use them with recursive glob
        files = []
        for pattern in file_patterns:
            files.extend(glob(pattern, recursive=True))
    else:
        # No files specified, return empty list
        files = []
    return list(set(files))

def adjust_command(cmd):
    os_type = platform.system()
    if os_type == 'Darwin':
        # Adjust sed -i 's/ //g' to sed -i '' 's/ //g'
        pattern = r"sed\s+-i\s+'([^']+)'"
        replacement = r"sed -i '' '\1'"
        cmd = re.sub(pattern, replacement, cmd)
    return cmd

# Function to validate files against the specified scope
def validate_scope(files, scope_patterns):
    for file in files:
        if not any(is_within_scope(file, pattern) for pattern in scope_patterns):
            return False
    return True

def is_within_scope(file, pattern):
    # Check if the file is within the directory or matches the file pattern
    if os.path.isdir(pattern):
        return os.path.commonpath([os.path.abspath(file), os.path.abspath(pattern)]) == os.path.abspath(pattern)
    else:
        return fnmatch(file, pattern)

def main():
    parser = argparse.ArgumentParser(description='An LLM-powered super-CLI.')
    parser.add_argument('command', nargs='+', help='The command to execute.')
    parser.add_argument(
        '-s', '--scope', nargs='*', default=['.'],
        help='Limit the scope of file context and modifications. Use "**/*.txt" for recursive patterns.'
    )
    args = parser.parse_args()

    # Handle restore and save commands
    if 'restore' in args.command:
        restore_files()
        sys.exit(0)
    elif 'save' in args.command:
        files = get_target_files(args.scope)
        if not files:
            print("No target files found to save.")
            sys.exit(1)
        save_backup(files)
        sys.exit(0)

    # Combine command line arguments into a prompt
    prompt = ' '.join(args.command)

    # Remove trailing slashes from each scope in args.scope
    args.scope = [scope.rstrip('/') for scope in args.scope]

    # Get plan, file change manifest, and instructions from LLM
    plan = get_instructions_and_files(prompt, args.scope)
    print(plan)
    # Parse the plan to extract files to modify and context files
    files_to_modify, context_files, instructions, execution_table = parse_plan(plan)
    # Print the parsed output for verification
    print("<supersed>")
    print("\nPlan received from Planner:")
    print("\nFiles to Modify/Create:")
    if files_to_modify:
        for file in files_to_modify:
            print(f"{file}")
    else:
        print("None (no files to modify)")

    print("\nContext Files:")
    if context_files:
        for file in context_files:
            print(f"{file}")
    else:
        print("None (no context files)")

    print("\nInstructions:")
    if instructions:
        print(f"{instructions}")
    else:
        print("None (no instructions provided)")

    print("\nExecution Table:")
    if execution_table:
        print(f"{execution_table}")
    else:
        print("None (no execution commands provided)")
    print()

    # Check if files are within the scope
    if not validate_scope(files_to_modify, args.scope) or not validate_scope(context_files, args.scope):
        print("Error: Some files are outside the specified scope.")
        sys.exit(1)

    # Only create backup if it doesn't already exist
    backup_files(files_to_modify)
    print()

    print("Executing command(s) from Planner instructions:")

    # Process commands based on the execution table
    commands = execution_table.splitlines()

    # Determine base directory from scope, default to current directory if not specified
    base_directory = args.scope[0] if args.scope else "."
    base_directory = os.path.dirname(base_directory) if os.path.isfile(base_directory) else base_directory
    for command in commands:
        command = command.strip()
        
        # Process lines that start with "COMMAND:"
        if command.startswith("COMMAND:"):
            actual_command = command.replace("COMMAND:", "").strip()
            print(f"Executing: {actual_command} in directory: {base_directory}")
            # Execute command in the determined base directory
            os.system(f"{actual_command}")

        # Process lines that start with "LLM:"
        elif command.startswith("LLM:"):
            llm_instruction = command.replace("LLM:", "").strip()
            print(f"Processing with LLM: {llm_instruction}")

            # Read contents of context files for use with LLM processing
            context_contents = read_file_contents(context_files)

            # Use the new helper function to parse and execute the LLM instruction
            process_llm_instruction(llm_instruction, context_contents)

if __name__ == "__main__":
    main()
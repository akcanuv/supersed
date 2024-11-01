#!/usr/bin/env python3

import os
import sys
import shutil
import argparse
import subprocess
from glob import glob
import re
import platform  # Import platform to detect OS

# Import OpenAI client
from openai import OpenAI

# Create the OpenAI client instance
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

if not client.api_key:
    print("Error: OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    sys.exit(1)

def backup_files(files, force=False):
    backup_dir = os.path.join(os.getcwd(), '.backup')
    if not os.path.exists(backup_dir) or force:
        for file in files:
            backup_path = os.path.join(backup_dir, file)
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy(file, backup_path)
        print("Backup created.")
    else:
        print("Backup already exists. Use 'supersed save' to update the backup.")

def save_backup(files):
    backup_dir = os.path.join(os.getcwd(), '.backup')
    for file in files:
        backup_path = os.path.join(backup_dir, file)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy(file, backup_path)
    print("Backup updated with current file versions.")

def restore_files():
    backup_dir = os.path.join(os.getcwd(), '.backup')
    if not os.path.exists(backup_dir):
        print("No backup found to restore.")
        return
    for root, _, files in os.walk(backup_dir):
        for file in files:
            backup_file = os.path.join(root, file)
            relative_path = os.path.relpath(backup_file, backup_dir)
            os.makedirs(os.path.dirname(relative_path), exist_ok=True)
            shutil.copy(backup_file, relative_path)
    print("Files restored from backup.")

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
            "You are supersed, a tool that analyzes user instructions and determines the steps needed to accomplish the task."
            "Under a section called 'Plan', provide a numbered list of steps to accomplish the task.\n"
            "Under a section called 'Files to Modify', provide an appropriate command using the scope that will display the relevant files needed to be modified when parsed, use `find`.\n" 
            "Under a section called 'Context Files', provide an appropriate command using the scope that will display the relevant files needed to be read for context when parsed, use `find`. Files that are to be updated must also be included in the context.\n" 
            "Under a section called 'Execution Table' provide a single step or a sequence of steps to be executed sequentially either with a `COMMAND: ` or an `LLM: ` prefix. \
            The 'COMMAND: ' prefix should be followed by the command to run using a CLI tool. \
            The COMMAND statements may include creation, deletion, copying, moving, executing and in-place modification of files within the given scope. \
            Example 1: 'COMMAND: sed -i '' '/^$/d; s/^[QA]: //' test/example_1.txt' \
            The 'LLM ' prefix should be followed by a generated prompt which is <instruction> to modify the required files. \
            The instructions, files_to_modify, context_files must be clearly seperated using <tags> followed by '{}'. The tags will be used to parse the message to be sent to the model. \
            They should be in a readable format such as: 'LLM 'Carry out the <instruction>{instruction} to modify the contents of <files_to_modify>{files_to_modify} using information in <context_files>{context_files}.''\n \
            Example 2: 'LLM: <instruction>{'Extract the details of the project from README.md and the dependencies from requirements.txt and \populate the fields in pyproject.toml'} of <files_to_modify>{'./pyproject.toml'} using information in <context_files>{'./pyproject.toml', './README.md', './requirements.txt'}.' \
            Example 3: 'LLM: For each file in <context_files>{'001.txt', '002.txt', '003.txt',...}, run <instruction>{'Correct the grammatical errors in the provided text and provide just the updated test. Do not include any additional explanation.'} and replace the contexts in <files_to_modify>{'001.txt', '002.txt', '003.txt',...}."
            "Provide clear sections for 'Plan', 'Files to Modify', 'Context Files' and 'Execution Table'." 
            "Do not include any additional explanation."
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

def parse_plan(plan):
    # Initialize lists
    files_to_modify = []
    context_files = []
    # Split the plan into lines
    lines = plan.split('\n')
    current_section = None

    for line in lines:
        line = line.strip()
        if line.lower() == 'files to modify:' or line.lower().startswith('files to modify'):
            current_section = 'modify'
            continue
        elif line.lower() == 'context files:' or line.lower().startswith('context files'):
            current_section = 'context'
            continue

        if current_section == 'modify':
            # Extract filenames from the line
            extracted = extract_filenames_from_text(line)
            files_to_modify.extend(extracted)
        elif current_section == 'context':
            extracted = extract_filenames_from_text(line)
            context_files.extend(extracted)

    return list(set(files_to_modify)), list(set(context_files)), plan

def process_with_llm(prompt, content, context_contents, filename):
    try:
        # Append context files content to the prompt
        context_text = ""
        for context_filename, file_content in context_contents.items():
            context_text += f"\n\n### Content of {context_filename}:\n{file_content}\n"
        full_prompt = f"Instruction: {prompt}\n\nContent of {filename} to Modify:\n{content}\n{context_text}"

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
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error processing with LLM: {e}")
        return content  # Return original content if there's an error

def generate_command_line_solution(prompt):
    try:
        system_prompt = (
            "You are a command-line assistant. Generate responses using 'Command:' and 'Explanation:' prefixes."
            " For each command needed to accomplish the task, start the line with 'Command:'."
            " For any explanations or descriptions, start the line with 'Explanation:'."
            " Do not include any other text or formats."
            " Do not use any code formatting such as backticks or code blocks."
            " Ensure that the commands are compatible with both GNU sed and BSD sed."
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        full_response = response.choices[0].message.content.strip()
        # Remove any markdown code blocks if present
        full_response = re.sub(r'```[a-z]*\n', '', full_response)
        full_response = re.sub(r'\n```', '', full_response)
        return full_response
    except Exception as e:
        print(f"Error generating command-line solution: {e}")
        return "Cannot generate command-line solution."

def generate_command_line_solution_for_file(prompt, filename):
    full_prompt = f"{prompt} (Target file: {filename})"
    try:
        system_prompt = (
            "You are a command-line assistant. Generate responses using 'Command:' and 'Explanation:' prefixes."
            " For each command needed to accomplish the task on the specified file, start the line with 'Command:'."
            " For any explanations or descriptions, start the line with 'Explanation:'."
            " Do not include any other text or formats."
            " Do not use any code formatting such as backticks or code blocks."
            " Ensure that the commands are compatible with both GNU sed and BSD sed."
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0
        )
        full_response = response.choices[0].message.content.strip()
        # Remove any markdown code blocks if present
        full_response = re.sub(r'```[a-z]*\n', '', full_response)
        full_response = re.sub(r'\n```', '', full_response)
        return full_response
    except Exception as e:
        print(f"Error generating command-line solution for {filename}: {e}")
        return "Cannot generate command-line solution."

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

def execute_commands(full_response):
    """
    Parses the LLM response and executes only the commands prefixed with 'Command:'.
    Ignores any lines starting with 'Explanation:' or other text.
    Also strips any backticks or extraneous characters from the commands.
    """
    commands = []
    lines = full_response.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith("Command:"):
            cmd = line[len("Command:"):].strip()
            # Remove surrounding backticks if present
            cmd = cmd.strip('`').strip()
            if cmd:
                commands.append(cmd)
    return commands

def main():
    parser = argparse.ArgumentParser(description='A natural language text editor powered by LLM.')
    parser.add_argument('command', nargs='+', help='The command to execute.')
    parser.add_argument('-s', '--scope', nargs='*', help='Limit the scope of context and file modifications. Use "**/*.txt" for recursive patterns.')
    args = parser.parse_args()

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

    prompt = ' '.join(args.command)

    # Get plan, file change manifest, instruction set from LLM
    plan = get_instructions_and_files(prompt, args.scope)
    print("Plan received from LLM:")
    print(plan)
    
    exit
    # Parse plan to get files to modify and context files
    files_to_modify, context_files, plan = parse_plan(plan)

    # Combine files from command line arguments and plan
    if args.scope:
        files = []
        for pattern in args.scope:
            files.extend(glob(pattern, recursive=True))
        files_to_modify = files  # Override files to modify with those specified in arguments

    if not files_to_modify:
        print("No target files specified to modify.")
        sys.exit(1)

    # Only create backup if it doesn't exist
    backup_files(files_to_modify)

    # Read contents of context files
    context_contents = read_file_contents(context_files)

    # Try to generate a global command-line solution first
    cmd = generate_command_line_solution(prompt)
    cmd = adjust_command(cmd)  # Adjust the command based on OS

    # Execute commands if a solution was generated
    if "Cannot generate command-line solution." not in cmd and cmd:
        print("Executing command(s):")
        commands = cmd.splitlines()
        for command in commands:
            command = command.strip()
            # Process only lines that start with "Command:"
            if command.startswith("Command:"):
                actual_command = command.replace("Command:", "").strip()
                print(f"Executing: {actual_command}")
                # Execute command in the correct directory
                os.system(actual_command.replace("cd test && ", ""))
    else:
        # Attempt to generate command-line solutions per file
        for file in files_to_modify:
            cmd = generate_command_line_solution_for_file(prompt, file)
            cmd = adjust_command(cmd)  # Adjust the command based on OS
            if "Cannot generate command-line solution." not in cmd and cmd:
                print(f"Executing command on {file}: {cmd}")
                # Replace placeholders and use file paths directly
                cmd = cmd.replace("[filename]", file).replace("<filename>", file)
                os.system(cmd)
            else:
                # Process file with LLM, including context contents
                if os.path.isfile(file):
                    with open(file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    edited_content = process_with_llm(prompt, content, context_contents, file)
                    with open(file, 'w', encoding='utf-8') as f:
                        f.write(edited_content)
                    print(f"Processed file with LLM: {file}")
                else:
                    print(f"File not found: {file}")

if __name__ == "__main__":
    main()
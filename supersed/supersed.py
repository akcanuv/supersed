#!/usr/bin/env python3

import os
import sys
import shutil
import argparse
import subprocess
import glob
import re
import platform  

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
        print("\nBackup already exists. Use 'supersed save' to update the backup.")

def save_backup(files):
    backup_dir = os.path.join(os.getcwd(), '.backup')
    for file in files:
        backup_path = os.path.join(backup_dir, file)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy(file, backup_path)
    print("\nBackup updated with current file versions.")

def restore_files():
    backup_dir = os.path.join(os.getcwd(), '.backup')
    if not os.path.exists(backup_dir):
        print("\nNo backup found to restore.")
        return
    for root, _, files in os.walk(backup_dir):
        for file in files:
            backup_file = os.path.join(root, file)
            relative_path = os.path.relpath(backup_file, backup_dir)
            os.makedirs(os.path.dirname(relative_path), exist_ok=True)
            shutil.copy(backup_file, relative_path)
    print("\nFiles restored from backup.")

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
            "Under a section called 'Files to Modify', provide an appropriate command using the scope that will display the relevant files needed to be modified when parsed, use `find`.\n" 
            "Under a section called 'Context Files', provide an appropriate command using the scope that will display the relevant files needed to be read for context when parsed, use `find`. Files that are to be updated must also be included in the context.\n" 
            "Under a section called 'Execution Table' provide a single step or a sequence of steps to be executed sequentially either with a `COMMAND: ` or an `LLM: ` prefix.\n"
            "The 'COMMAND: ' prefix should be followed by the command to run using a CLI tool. The COMMAND statements may include creation, deletion, copying, moving, executing and in-place modification of files within the given scope.\n"
            "Example 1: 'COMMAND: sed -i '' '/^$/d; s/^[QA]: //' test/example_1.txt'\n"
            "The 'LLM: ' prefix should be followed by a generated prompt which is <instruction> to modify the required files. The instructions, files_to_modify, context_files must be clearly seperated using <tags> followed by '{}'. The tags will be used to parse the message to be sent to the model. They should be in a readable format such as: 'LLM 'Carry out the <instruction>{instruction} to modify the contents of <files_to_modify>{files_to_modify} using information in <context_files>{context_files}.''\n" 
            "Example 2: 'LLM: <instruction>{'Extract the details of the project from README.md and the dependencies from requirements.txt and \populate the fields in pyproject.toml'} of <files_to_modify>{'./pyproject.toml'} using information in <context_files>{'./pyproject.toml', './README.md', './requirements.txt'}.'\n" 
            "Example 3: 'LLM: For each file in <context_files>{'001.txt', '002.txt', '003.txt',...}, run <instruction>{'Correct the grammatical errors in the provided text and provide just the updated test. Do not include any additional explanation.'} and replace the contexts in <files_to_modify>{'001.txt', '002.txt', '003.txt',...}.\n"
            "When processing more than one file with LLM, modify the <instruction> assuming it is only acting on one file at a time, so it should not reference any files in <instruction>.\n"
            "<context_files> and <files_to_modify> may be a `find` command for user instructions such as a file pattern or when 'all files' is mentioned"
            "Provide clear sections for 'Plan', 'Files to Modify', 'Context Files' and 'Execution Table'. Do not enclose the sections with markdown code blocks.\n" 
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

def extract_filenames_from_text(line):
    # Extracts filenames from a line of text by searching for patterns like file paths
    return re.findall(r'[./\w-]+(?:\.\w+)?', line)

def parse_plan(plan, scope=None):
    # Initialize lists for sections
    files_to_modify = []
    context_files = []
    instructions = ""
    execution_table = ""
    current_section = None

    # Ensure scope is a single path, not a list
    if isinstance(scope, list):
        scope = scope[0] if scope else "."

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
            extracted_files = execute_find_command(line, scope) if line else []
            files_to_modify.extend(extracted_files)
        elif current_section == 'context':
            # Handle cases where Context Files is explicitly marked as empty
            if line.lower() == '- none':
                continue
            extracted_files = execute_find_command(line, scope) if line else []
            context_files.extend(extracted_files)
        elif current_section == 'execute':
            execution_table += line + "\n"
    # Return parsed elements, ensure deduplication and clean formatting
    return list(set(files_to_modify)), list(set(context_files)), instructions.strip(), execution_table.strip()

def execute_find_command(command_line, scope="."):
    try:
        # Only proceed if command_line is valid and contains 'find'
        if not command_line or "find" not in command_line:
            print(f"Skipping invalid command: {command_line}")
            return []
        
        # Check if command_line starts with "COMMAND:" and modify it to start from the scope directory
        if command_line.startswith("COMMAND:"):
            command_line = command_line.replace("COMMAND: find", f"find", 1).strip()
        
        # Execute the command and capture the output
        result = subprocess.run(command_line, shell=True, text=True, capture_output=True, check=True)
        
        # Split the output by lines to get individual file paths
        files = result.stdout.strip().split('\n')
        
        # Filter out any empty strings in case there are blank lines in the output
        return [file for file in files if file]
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command_line}")
        print(e.stderr)  # Output the error message for debugging
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

def execute_commands(full_response):
    """
    Parses the LLM response and executes only the commands prefixed with 'COMMAND:'.
    Ignores any lines starting with 'Explanation:' or other text.
    Also strips any backticks or extraneous characters from the commands.
    """
    commands = []
    lines = full_response.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith("COMMAND:"):
            cmd = line[len("COMMAND:"):].strip()
            # Remove surrounding backticks if present
            cmd = cmd.strip('`').strip()
            if cmd:
                commands.append(cmd)
    return commands

def main():
    parser = argparse.ArgumentParser(description='A natural language text editor powered by LLM.')
    parser.add_argument('command', nargs='+', help='The command to execute.')
    parser.add_argument(
        '-s', '--scope', nargs='*', default=['.'],
        help='Limit the scope of file modifications. Use "**/*.txt" for recursive patterns.'
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

    # Get plan, file change manifest, and instructions from LLM
    plan = get_instructions_and_files(prompt, args.scope)
    print("Plan received from LLM:")
    print(plan)
    # Parse the plan to extract files to modify and context files
    files_to_modify, context_files, instructions, execution_table = parse_plan(plan, scope=args.scope)
    # Print the parsed output for verification
    print("\nFiles to Modify:")
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

    if not files_to_modify:
        print("\nNo target files match the specified scope or the files do not exist.")

    # Only create backup if it doesn't already exist
    backup_files(files_to_modify)

    # Read contents of context files for use with LLM processing
    context_contents = read_file_contents(context_files)

    print("Executing command(s) from LLM instructions:")

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

            # Use the new helper function to parse and execute the LLM instruction
            process_llm_instruction(llm_instruction, context_contents)

if __name__ == "__main__":
    main()
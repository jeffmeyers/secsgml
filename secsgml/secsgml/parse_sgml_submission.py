import os
import uu
from io import BytesIO
from itertools import dropwhile

def detect_submission_type(first_line):
    if first_line.startswith('<SUBMISSION>'):
        return 'dashed-default'
    elif first_line.startswith('-----BEGIN PRIVACY-ENHANCED MESSAGE-----'):
        return 'tab-privacy'
    elif first_line.startswith('<SEC-DOCUMENT>'):
        return 'tab-default'
    else:
        raise ValueError('Unknown submission type')
    
def parse_header_metadata(lines, submission_type):
    """We pass in first line to line before first <DOCUMENT> tag"""
    header_metadata = {}
    
    if submission_type == 'dashed-default':
        current_dict = header_metadata
        stack = [(header_metadata, None)]  # (dict, tag) pairs
        i = 0
        
        while i < len(lines):
            line = lines[i]
            # get 0 to first '>'
            tag, text = line.split('>')
            tag = tag[1:].lower()  # Remove '<' and convert to lowercase
            text = text.strip()
            
            # Handle closing tags
            if tag.startswith('/'):
                tag = tag[1:]  # Remove the '/'
                if stack and stack[-1][1] == tag:
                    stack.pop()
                    current_dict = stack[-1][0] if stack else header_metadata
                i += 1
                continue
            
            # Look ahead for matching closing tag
            is_paired = False
            for j in range(i + 1, len(lines)):
                if lines[j].strip().lower().startswith(f'</{tag.lower()}>'):
                    is_paired = True
                    break
            
            if is_paired:
                # This is a paired tag - create nested structure
                nested_dict = {}
                
                # Handle key collision for nested structures
                if tag in current_dict:
                    if isinstance(current_dict[tag], list):
                        current_dict[tag].append(nested_dict)
                    else:
                        current_dict[tag] = [current_dict[tag], nested_dict]
                else:
                    current_dict[tag] = nested_dict
                
                # Update stack and current_dict
                stack.append((nested_dict, tag))
                current_dict = nested_dict
                
            else:
                # Only add unpaired tags if they have non-empty text
                if text != '':
                    # This is an unpaired tag - handle normally
                    if tag in current_dict:
                        if isinstance(current_dict[tag], list):
                            current_dict[tag].append(text)
                        else:
                            current_dict[tag] = [current_dict[tag], text]
                    else:
                        current_dict[tag] = text
            
            i += 1
    elif submission_type == 'tab-default' or submission_type == 'tab-privacy':
        current_dict = header_metadata
        stack = [(0, header_metadata)]  # (indent_level, dict) pairs

        if submission_type == 'tab-privacy':
            privacy_message = []
            i = 0
            for i, line in enumerate(lines):
                if line.strip() == '-----BEGIN PRIVACY-ENHANCED MESSAGE-----':
                    # Capture everything until we hit a blank line or any tag (< followed by uppercase)
                    j = i + 1
                    while j < len(lines):
                        line = lines[j]
                        if (line.strip() == '' or 
                            ('<' in line and any(c.isupper() for c in line[line.find('<')+1:]))):
                            break
                        privacy_message.append(line.strip())
                        j += 1
                    header_metadata['privacy-enhanced-message'] = '\n'.join(privacy_message)
                    lines = lines[j:]  # Continue processing from after privacy section
                    break
        
        for line in lines:
            # ignore empty lines
            if line.strip() == '':
                continue
            
            indent = len(line) - len(line.lstrip())
            tag, text = line.split(':')
            
            # Clean up tag and text
            tag = tag.strip()
            if '>' in tag:
                tag = tag[tag.find('<')+1:tag.find('>')].lower()
            else:
                tag = tag.lower()
            text = text.strip()
            
            # Pop stack while at same or lower indent level
            while len(stack) > 1 and stack[-1][0] >= indent:
                stack.pop()
            
            current_dict = stack[-1][1]
            
            # Only add if text is not empty
            if text:
                if tag in current_dict:
                    if isinstance(current_dict[tag], list):
                        current_dict[tag].append(text)
                    else:
                        current_dict[tag] = [current_dict[tag], text]
                else:
                    current_dict[tag] = text
            else:
                # This is a parent node 
                # First pop any existing stack levels at same indent
                while len(stack) > 1 and stack[-1][0] == indent:
                    stack.pop()
                
                nested_dict = {}
                if tag in current_dict:
                    if isinstance(current_dict[tag], list):
                        current_dict[tag].append(nested_dict)
                    else:
                        current_dict[tag] = [current_dict[tag], nested_dict]
                else:
                    current_dict[tag] = nested_dict
                
                stack.append((indent, nested_dict))
                current_dict = nested_dict
    
    return header_metadata

        

def detect_uu(first_line):
    """Detect if the document is uuencoded"""
    first_line = first_line.strip()
    if first_line.startswith('begin'):
        return True
    else:
        return False
    
def clean_lines(lines):
    """Clean lines by removing leading and trailing whitespace as well as special tags"""
    # Find first non-empty line and remove prefix
    lines = list(dropwhile(lambda x: not x.strip(), lines))
    
    # Handle special tags if present
    if lines and lines[0].strip() in ['<PDF>', '<XBRL>', '<XML>']:
        # Find matching closing tag
        tag = lines[0].strip()[1:-1]  # Extract tag name without brackets
        end_tag = f'</{tag}>'

        # Remove opening tag
        lines = lines[1:]
        
        # Keep only content up to closing tag if found
        try:
            last_idx = next(i for i, line in enumerate(reversed(lines)) 
                          if line.strip() == end_tag)
            lines = lines[:-last_idx-1]
        except StopIteration:
            pass  # No closing tag found
            
    return lines

def parse_text_tag_contents(lines, output_path):
    """Write the contents of a <TEXT> tag to a file"""
    lines = clean_lines(lines)

    content = '\n'.join(lines)
    # Check for UUencoded file
    if detect_uu(lines[0]):
        # handle uuencoded file
        with BytesIO(content.encode()) as input_file:
                uu.decode(input_file, output_path, quiet=True)
    else:
        # write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

# LOOK HERE AND REWRITE

def get_documents(lines):
    documents = []
    current_doc = []
    in_document = False
    
    for line in lines:
        if line.strip() == '<DOCUMENT>':
            in_document = True
            # Skip the DOCUMENT tag itself
            continue
        elif line.strip() == '</DOCUMENT>':
            in_document = False
            # Join and add the completed document
            documents.append(''.join(current_doc))
            current_doc = []
        elif in_document:
            current_doc.append(line)
            
    return documents


    

def parse_sgml_submission(content = None, filepath = None,output_dir = None):
    if not filepath and not content:
        raise ValueError("Either filepath or content must be provided")
    
    os.makedirs(output_dir, exist_ok=True)

    # we will read the accension number, remove the dashes and use it to create the folder

    # If content not provided, read from file
    if content is None:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

    # Split into Lines
    lines = content.splitlines(keepends=True)

    # Split lines into header and documents
    header_start = lines.index('<DOCUMENT>')
    header = lines[:header_start]
    
    # documents
    documents = get_documents(lines[header_start:])


            
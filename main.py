import os
import logging
import sys
import subprocess
import time
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def env_setup():
    """
        Prompt for OPENAI_API_KEY and save it to a .env file if not already present.
    """
    # Load existing environment variables
    dotenv_path = '.env'
    load_dotenv(dotenv_path=dotenv_path)

    # Check if the OPENAI_API_KEY is already set
    if not os.getenv('OPENAI_API_KEY'):
        # If not set, prompt the user to enter it
        api_key = input("Please enter your OPENAI_API_KEY: ").strip()
        
        # Append or create the .env file with the OPENAI_API_KEY
        with open(dotenv_path, 'a') as f:
            f.write(f'OPENAI_API_KEY="{api_key}"\n')
        
        # Update the current environment variable for this execution
        os.environ['OPENAI_API_KEY'] = api_key
        print("API Key saved to .env file and loaded for this session.")

def initialize_openai_client():
    """
    Initialize OpenAI client.
    """
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set in environment variables.")

    return OpenAI(api_key=OPENAI_API_KEY)

def create_assistant(client):
    """
    Create an Assistant.
    """
    assistant = client.beta.assistants.create(
        name="AI-PenTest-Tool",
        instructions="""
        You are a Cyber Security Specialist. Respond with only the necessary penetration testing commands. Your responses should only be code, without explanation or formatting
        - When provided with an IP, give initial reconnaissance commands.
        - Provide 1 command at a time.
        - Do not send another command until you receive the results of the previous command
        - For subsequent steps, provide relevant commands based on the results provided.
        - The mid-term goal is to determine as many vulnerabilites as possible.
        - The end goal is to exploit this vulnerabilites
        - Avoid using user interaction required commands.
        - When you have exhausted all your penetration testing resources, you should respond with "Done"
        Commands should be presented plainly: command
        """,
        tools=[{"type": "code_interpreter"}],
        model="gpt-4-turbo-preview"
    )
    return assistant.id

def create_thread(client):
    """
    Create a new thread.
    """
    return client.beta.threads.create()

def send_message(client, thread_id, content):
    """
    Send a message in the thread.
    """
    return client.beta.threads.messages.create(thread_id=thread_id, role="user", content=content)

def list_messages(client, thread_id):
    """
    List messages in a thread.
    """
    return client.beta.threads.messages.list(thread_id=thread_id)

def create_run(client, thread_id, assistant_id):
    """
    Create a Run.
    """
    return client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id,)

def check_run_status(client, run_id, thread_id):
    """
    Check the run status.
    """
    return client.beta.threads.runs.retrieve(run_id=run_id, thread_id=thread_id)

def is_pen_test_complete(message):
    """
    Determine if the pen test is complete
    """
    return message.strip().lower() == "done"

def get_assistant_responses(client, thread_id, assistant_id):
    """
    Retrieve only the assistant's responses from a thread.
    """
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    assistant_responses = [msg for msg in messages.data if msg.assistant_id == assistant_id]
    return assistant_responses

def execute_command(command):
    """
    Execute a shell command and return its output and error separately, 
    and write the output to a specified file, also print the command and its output.
    """
    print(f"Executing command: {command}")  # Debugging print
    base_command = command.split()[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{base_command}_results_{timestamp}.txt"
    try:
        # Ensure the command is safe to execute (optional, based on use case)
        # if not is_command_safe(command):
        #     logging.error(f"Command is not safe to execute: {command}")
        #     return

        with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc, open(filename, 'w') as file:
            for line in proc.stdout:
                print(line, end='')
                file.write(line)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing command: {e}")
    except FileNotFoundError:
        logging.error(f"Command not found: {base_command}")
    except OSError as e:
        logging.error(f"OS error occurred: {e}")
    except Exception as e:
        logging.error(f"Unexpected error executing command: {e}")
    return filename

def main(ip_address):
    # Initialization of client, assistant and thread
    client = initialize_openai_client()
    assistant_id = create_assistant(client)
    thread = create_thread(client)

    send_message(client,thread.id, f"Start a penetration test on this machine {ip_address}.")
    run = create_run(client, thread.id, assistant_id)
    
    # Main Loop
    while True:
        # Wait for assistant's response
        while True:
            run_status = check_run_status(client, run.id, thread.id)
            if run_status.status == "completed":
                assistant_responses = get_assistant_responses(client, thread.id, assistant_id)
                if assistant_responses:
                    message_content = assistant_responses[0].content[0].text.value
                break
            time.sleep(10)

        if is_pen_test_complete(message_content):
            print("Penetration Testing is complete.")
            break

        filename = execute_command(message_content)
        with open(filename, 'r') as file:
            file_content = file.read()
            send_message(client, thread.id, file_content)
            run = create_run(client, thread.id, assistant_id)


if __name__ == "__main__":
    # Check for IP address
    if len(sys.argv) > 1:
        ip_address = sys.argv[1]
        env_setup()
        main(ip_address)
    else:
        print("Please provide an IP address")
        sys.exit(1)

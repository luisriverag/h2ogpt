import json
import os
import argparse
import sys
import time

if 'src' not in sys.path:
    sys.path.append('src')


def get_rag_answer(prompt, text_context_list=None, image_files=None, chat_conversation=None,
                   model=None,
                   system_prompt=None,
                   max_tokens=1024,
                   temperature=0,
                   stream_output=True,
                   max_time=120):
    base_url = os.getenv('H2OGPT_OPENAI_BASE_URL')
    assert base_url is not None, "H2OGPT_OPENAI_BASE_URL environment variable is not set"
    server_api_key = os.getenv('H2OGPT_OPENAI_API_KEY', 'EMPTY')

    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=server_api_key, timeout=max_time)

    from openai_server.backend_utils import structure_to_messages
    messages = structure_to_messages(prompt, system_prompt, chat_conversation, image_files)

    extra_body = {}
    if text_context_list:
        extra_body['text_context_list'] = text_context_list

    responses = client.chat.completions.create(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream_output,
        extra_body=extra_body,
    )
    text = ''
    tgen0 = time.time()
    verbose = True
    print("\nENDOFTURN\n")
    print("\n\n#### Begin RAG Answer\n\n")
    for chunk in responses:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            text += delta
            print(delta, end='', flush=True)
        if time.time() - tgen0 > max_time:
            if verbose:
                print("\nTook too long for OpenAI or VLLM Chat: %s" % (time.time() - tgen0),
                      flush=True)
            break
    print("\n\n#### End RAG Answer")
    print("\nENDOFTURN\n")
    return text


def main():
    default_max_time = int(os.getenv('H2OGPT_AGENT_OPENAI_TIMEOUT', "120"))
    text_context_list_file = os.getenv('H2OGPT_RAG_TEXT_CONTEXT_LIST')
    chat_conversation_file = os.getenv('H2OGPT_RAG_CHAT_CONVERSATION')
    system_prompt_file = os.getenv('H2OGPT_RAG_SYSTEM_PROMPT')
    b2imgs_file = os.getenv('H2OGPT_RAG_IMAGES')

    if text_context_list_file:
        with open(text_context_list_file, "rt") as f:
            text_context_list = []
            for line in f:
                text_context_list.append(line)
    else:
        text_context_list = []

    if chat_conversation_file:
        with open(chat_conversation_file, "rt") as f:
            chat_conversation = json.loads(f.read())
    else:
        chat_conversation = []
    if system_prompt_file:
        with open(system_prompt_file, "rt") as f:
            system_prompt = f.read()
    else:
        system_prompt = ''
    image_files = []
    if b2imgs_file:
        with open(b2imgs_file, "rt") as f:
            for line in f:
                image_files.append(line)
    else:
        image_files = []

    parser = argparse.ArgumentParser(description="RAG Tool")
    parser.add_argument("-p", "--prompt", type=str, required=True, help="User prompt")
    parser.add_argument("-b", "--baseline", required=False, action='store_true',
                        help="Whether to get baseline from user docs")
    parser.add_argument("--files", nargs="+", required=False,
                        help="Files of documents as textual files with optionally additional images")
    parser.add_argument("-m", "--model", type=str, required=False, help="OpenAI or Open Source model to use")
    parser.add_argument("--max_time", type=float, required=False, default=default_max_time,
                        help="Maximum time to wait for response")
    parser.add_argument("--system_prompt", type=str, required=False, default=system_prompt, help="System prompt")
    parser.add_argument("--chat_conversation_file", type=str, required=False,
                        help="chat history json list of tuples with each tuple as pair of user then assistant text messages.")
    args = parser.parse_args()

    if not args.model:
        args.model = os.getenv('H2OGPT_AGENT_OPENAI_MODEL')
    if not args.model:
        raise ValueError("Model name must be provided via --model or H2OGPT_AGENT_OPENAI_MODEL environment variable")

    if args.chat_conversation_file:
        with open(args.chat_conversation_file, "rt") as f:
            chat_conversation = json.loads(f.read())

    if args.files:
        from src.vision.utils_vision import IMAGE_EXTENSIONS
        text_context_list = []
        for filename in args.files:
            if filename.endswith('.txt'):
                with open(filename, "rt") as f:
                    text_context_list.append(f.read())
            elif any(filename.endswith(x) for x in IMAGE_EXTENSIONS):
                image_files.append(filename)

    rag_kwargs = dict(text_context_list=text_context_list,
                      image_files=image_files,
                      chat_conversation=chat_conversation,
                      model=args.model,
                      system_prompt=args.system_prompt, max_time=args.max_time)

    # Get the RAG answer
    print("<simple_rag_answer>")
    rag_answer = get_rag_answer(args.prompt, **rag_kwargs)
    print("</simple_rag_answer>")
    if rag_answer:
        print(
            "The above simple_rag_answer answer may be correct, but the answer probably requires validation via checking the documents for similar text or search and news APIs if involves recent events.  Note that the LLM answering above has no coding capability or internet access so disregard its concerns about that if it mentions it.")


if __name__ == "__main__":
    main()

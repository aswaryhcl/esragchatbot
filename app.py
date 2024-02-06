import azure.functions as func
import logging
import openai
from openai import AzureOpenAI
import requests
import json, os
import traceback
from dotenv import load_dotenv, find_dotenv
from elasticsearch import Elasticsearch
from langchain.memory import ElasticsearchChatMessageHistory
# from langchain.vectorstores import ElasticsearchStore
from langchain_community.vectorstores import ElasticsearchStore
from logger import LOG, handle_error
from es_client import ES_Client, textExpansion_Search, RetrieveESresults
from llm import AzureOpenAi_Client, ChatCompletion, ChatCompletionStream, GeneratedResponse
from text_normalizer import normalize_text
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
print('running app')

load_dotenv(find_dotenv())

# Load Env Variables
LLM_TYPE = os.getenv("LLM_TYPE")
ES_INDEX = os.getenv("ES_INDEX")
top_n_results=os.getenv("top_n_results")

print('LLM_TYPE: {0}'.format(LLM_TYPE))
streaming=False


system_prompt="-- You are an AI assistant which answers user's questions in a concise manner.\n-- Your job is to respond to the question strictly by reference to the Source, a passage of text you will be provided.\n-- If the response content contains pointers, then generate the response in pointers as well but in a concise manner.\n -- always answer in natural human way.\n --Always give concise answers.\n-- If you don't know the answer, just say that you don't know, don't try to make up an answer.\n -- Aim to answer queries using existing conversational context."

messages = [{ "role": "system", "content": system_prompt }]


@app.route('/', methods=['GET','POST'])
def index():
    print('inside index function')

    if request.method == "POST":

        # if input from ajax is a text value from a form input with id = input :::
        question = request.form['input']
        if not question:
            try:
                req_body = req.get_json()
            except ValueError:
                pass
            else:
                question = req_body.get('question')
    
        if question:
            if len(question) > 1:
            
                user_prompt = {
                    "role": "user",
                    "content": question
                    }
    
                print('User Question Prompt:\n{0}'.format(user_prompt['content']))
    
                messages.append(user_prompt)
    
                # get top results from ES semantic search
                top_hit_responses=RetrieveESresults(question, ES_INDEX, top_n_results)
    
                final_result_set={}
                if len(top_hit_responses)>0:
                    final_result_set['top_source']=top_hit_responses[0]['doc_id']
                    final_result_set['top_score']=top_hit_responses[0]['score']
                    final_result_set['top_answer']=top_hit_responses[0]['body']
                    final_result_set['second_best_source']=top_hit_responses[1]['doc_id']
                    final_result_set['second_best_score']=top_hit_responses[1]['score']
                    #print(type(final_result_set))
                    #print(final_result_set['top_answer'])
                    output_answer=normalize_text(final_result_set['top_answer'])
                    #print(output_answer)
                else:
                    output_answer='Greet the user. Ask the user how can you assist them with anything related to SNOW'
                    messages[1]['content']=''
                    final_result_set['top_source']=None
                    final_result_set['top_score']=None
    
                # Create Assistant content for OpenAI
                Assistant_Content={
                    'role': 'assistant',
                    'content': output_answer
                    }
    
                print('ES semantic Search Result:\n{0}'.format(Assistant_Content['content']))
    
                messages.append(Assistant_Content)
    
                print(messages)
    
                OpenAIoutput=GeneratedResponse(messages,is_stream=False)
                LOG.info('OpenAI Results::\n\t{0}'.format(str(OpenAIoutput)))
    
                # LOG.info('OpenAI Results::\n\tcontent:::\t{0}\n\tPrompt Tokens:::\t{1}\n\tOutput Tokens:::\t{2}'.format(OpenAIoutput['content'], OpenAIoutput['prompt_tokens'], OpenAIoutput['output_tokens']))
                #print(response)
    
                ai_response={
                                'output': OpenAIoutput['content'], 
                                'source': final_result_set['top_source']
                            }

                return jsonify(ai_response)
                                    
    
            return jsonify({'output' : 'Unable to identify any input..'})
        
        else:
            return jsonify({'output' : 'Unable to identify any input..'})
            
    return render_template('index.html')

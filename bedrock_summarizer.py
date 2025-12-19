import json
import boto3

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def summarize_json(json_text):
    prompt = f"Summarize this JSON data in one sentence: {json_text}"
    
    body = json.dumps({
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 100,
            "temperature": 0.1
        }
    })
    
    response = bedrock.invoke_model(
        body=body,
        modelId='amazon.titan-text-express-v1',
        accept='application/json',
        contentType='application/json'
    )
    
    result = json.loads(response['body'].read())
    return result['results'][0]['outputText'].strip()

# Usage
if __name__ == "__main__":
    sample_json = '{"regulation": "482.1", "title": "Hospital conditions", "requirements": ["staffing", "safety"]}'
    summary = summarize_json(sample_json)
    print(summary)
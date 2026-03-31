import os, openai

client = openai.OpenAI(
  api_key=os.environ["ASI_API_KEY"],
  base_url="https://inference.asicloud.cudos.org/v1"
)

def useMiniMax(content):
    resp = client.chat.completions.create(
      model="minimax/minimax-m2.5",
      messages=[{"role":"user","content":content}],
      max_tokens=6000
    )
    return resp.choices[0].message.content.replace("_quote_",'"').replace("_apostrophe_","'")

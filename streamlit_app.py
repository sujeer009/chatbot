import streamlit as st
import requests
import time
import pandas as pd 

# === CONFIG ===
DATABRICKS_INSTANCE = "adb-5264822104976956.16.azuredatabricks.net"
SPACE_ID = "01f01f62db311ee28190e4d40e204314"
TOKEN = "dapi86341d8576e3324ae97ef589b00a87b5"  # Store your PAT in Streamlit secrets


API_BASE = f"https://{DATABRICKS_INSTANCE}/api/2.0/genie/spaces/{SPACE_ID}"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# === UI SETUP ===
st.set_page_config(page_title="Chat with Genie", layout="centered")
st.title("Chat with Databricks Genie")

# === SESSION STATE ===
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conv_id" not in st.session_state:
    st.session_state.conv_id = None

df = pd.DataFrame()  # Initialize empty DataFrame for results
df_data = []  # List to store DataFrames for each response

# === USER INPUT ===
user_input = st.chat_input("Ask Genie...")

if user_input:
    # === DISPLAY CHAT HISTORY ===
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            st.dataframe(df_data[m], use_container_width=True)
            
                
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Display user input in chat
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Step 1: Start conversation or continue
    if not st.session_state.conv_id:
        url = f"{API_BASE}/start-conversation"
    else:
        url = f"{API_BASE}/conversations/{st.session_state.conv_id}/messages"
        st.write("Continuing conversation...") # Debugging line
        

    payload = {"content": user_input}

    with st.spinner("Genie is thinking..."):
        response = requests.post(url, headers=HEADERS, json=payload)
        if response.status_code != 200:
            st.error("Failed to send message to Genie")
            st.text(response.text)
            st.stop()

        data = response.json()
        st.session_state.conv_id = data["conversation_id"]
        message_id = data["message_id"]

        # Step 2: Poll for completion
        poll_url = f"{API_BASE}/conversations/{st.session_state.conv_id}/messages/{message_id}"

        status = "SUBMITTED"
        while status not in ("COMPLETED", "FAILED", "CANCELLED"):
            time.sleep(2)
            poll_resp = requests.get(poll_url, headers=HEADERS)
            message = poll_resp.json()
            status = message.get("status")
        
    # Step 3: Check for attachments
    
    attachments = message.get("attachments", [])

    if not attachments:
        answer = "(No response from Genie)"
    else:
        attachment = attachments[0]
        if "text" in attachment:
            answer = attachment["text"]["content"]
        elif "query" in attachment:
            q = attachment["query"]
            answer = f"🔍 {q.get('description')}\n\n```sql\n{q.get('query')}\n```"
        else:
            answer = "(Unrecognized format)"
        # Case A: Direct content
        if "attachment_id" not in attachment:
            answer = "(No attachment ID found in response)"
        # Case B: Get via /query-result
        else:
            attachment_id = attachment["attachment_id"]
            result_url = f"{poll_url}/query-result/{attachment_id}"
            result_resp = requests.get(result_url, headers=HEADERS)
            if result_resp.status_code != 200:
                answer = "(Error fetching result from Genie)"
            else:
                result = result_resp.json()
                try:
                    columns = [col['name'] for col in result['statement_response']['manifest']['schema']['columns']]
                    data = result['statement_response']['result']['data_array']
                    df = pd.DataFrame(data, columns=columns)
                                     
                except Exception as e:
                    df = pd.DataFrame()
                    answer = "No data returned from Genie."
                    # st.error("❌ Failed to parse result.")
                    # st.text(str(e))
                # if "text" in result:
                #     answer = result["text"]["content"]
                # elif "query" in result:
                #     q = result["query"]
                #     answer = f"🔍 {q.get('description')}\n\n```sql\n{q.get('query')}\n```"
                # else:
                #     answer = "(Unsupported format)"

    st.session_state.messages.append({"role": "assistant", "content": answer})
    df_data.append(df)   
    # Display response in chat
    with st.chat_message("assistant"):
        st.markdown(answer)
        if df.empty:  
            st.write("No data returned from Genie.")              
        else:
            st.dataframe(df, use_container_width=True)




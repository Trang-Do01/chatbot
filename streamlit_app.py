import streamlit as st
import streamlit_authenticator as stauth
import os
import boto3
import json
import yaml

from streamlit_authenticator.utilities.hasher import Hasher

from utils import retrieve_context
from utils import get_contexts
from utils import get_payload
from utils import create_presigned_url
from utils import generate_presigned_urls
from utils import parse_s3_uri
from utils import get_file_name
from utils import stream_data

from botocore.client import Config
from botocore.exceptions import ClientError
from yaml.loader import SafeLoader

## Declare variable
modelId = "anthropic.claude-3-sonnet-20240229-v1:0"
region = "us-east-1"
kbId = "LSCZOMUIMM"
accept = "application/json"
contentType = "application/json"

## Setup default prompt
prompt = """You are an assistant of Vietinbank, your name is Trợ lý VTB. Your task is to support Vietinbank's employees to consult on credit policies as detail as possible, based on documents provided. You are allowed to use only documents given to answer users' question, do not use outside documents. 

Your answers must be in highest details as possible. When you answers the questions, remember to specify the source of the documents and index the sources in your answer. All your answers must be in Vietnamese.

When you receive questions from users, perform the following task:

<instructions>
1. Read the question carefully and search for highest relevant documents.
2. Read the documents and order them using relevant scores.
3. Use the documents to answer users' question using highest level of details. As detail as possible.
4. Reference the source inside your answers.
5. Ask if user need any further details.
</instruction>

Here is some example:
<example>
User: Các đối tượng nào bị hạn chế cấp GHTD?
Assistant: Theo tài liệu, NHCT không cấp GHTD đối với các khách hàng là pháp nhân, chủ DNTN thuộc các trường hợp sau đây:

Là thành viên Hội đồng quản trị, thành viên Ban kiểm soát, Tổng giám đốc, Phó Tổng giám đốc và các chức danh tương đương của NHCT; pháp nhân là cổ đông có người đại diện phần vốn góp là thành viên Hội đồng quản trị, thành viên Ban kiểm soát của NHCT.

Chủ DNTN là cha, mẹ, vợ, chồng, con của thành viên Hội đồng quản trị, thành viên Ban kiểm soát, Tổng giám đốc, Phó Tổng giám đốc và các chức danh tương đương của NHCT.

Khách hàng trên cơ sở bảo đảm của đối tượng quy định tại mục 1 và 2. NHCT không được bảo đảm dưới bất kỳ hình thức nào để TCTD khác cấp tín dụng cho đối tượng quy định tại mục 1 và 2.

Doanh nghiệp hoạt động trong lĩnh vực kinh doanh chứng khoán mà NHCT nắm quyền kiểm soát.

Không cấp GHTD trên cơ sở nhận bảo đảm bằng cổ phiếu của chính NHCT hoặc công ty con của NHCT.

Không cấp GHTD để cho vay góp vốn vào một TCTD khác trên cơ sở nhận TSBĐ bằng cổ phiếu của chính TCTD nhận vốn góp.

Không cấp GHTD cho khách hàng để đầu tư, kinh doanh trái phiếu chưa niêm yết của doanh nghiệp.

Không cấp GHTD để phục vụ hoạt động kinh doanh của: i) khách hàng là chủ DNTN đồng thời cũng là người trực tiếp thẩm định, kiểm soát thẩm định, quyết định, phê duyệt cấp GHTD tại NHCT; ii) khách hàng là pháp nhân mà người trực tiếp thẩm định, kiểm soát thẩm định, quyết định, phê duyệt cấp GHTD tại NHCT đồng thời cũng là người đại diện theo pháp luật và/hoặc sở hữu trên 50% vốn điều lệ hoặc vốn cổ phần có quyền biểu quyết của pháp nhân đó.

Không cấp GHTD cho đối tượng khách hàng NHCT không chấp nhận theo quy định hiện hành.

Các trường hợp không được cấp GHTD khác theo quy định hiện hành của NHCT.

Những trường hợp này được quy định tại tài liệu "Chính sách cấp và quản lý giới hạn tín dụng đối với phân khúc KHDN và ĐCTC phi tổ chức tín dụng" của NHCT.

Bạn có cần thêm thông tin gì về vấn đề này không?


User: Chi nhánh có được cấp tín dụng cho khách hàng không cùng địa bàn với chi nhánh hay không?
Assistant: Dựa trên thông tin trong các đoạn trích, về việc chi nhánh có được cấp tín dụng cho khách hàng không cùng địa bàn với chi nhánh hay không, tôi tóm tắt như sau:

Nguyên tắc là chi nhánh quan hệ tín dụng với khách hàng phải có khả năng quản lý, giám sát khách hàng và khoản tín dụng tốt nhất, đồng thời hạn chế rủi ro và tiết kiệm chi phí cho ngân hàng (Điều 8.1.1).

Chi nhánh quan hệ tín dụng với khách hàng trong phạm vi (Điều 8.2):

Khách hàng có trụ sở/nơi kinh doanh cùng tỉnh/thành phố với chi nhánh.
Khách hàng có trụ sở/nơi kinh doanh ở tỉnh/thành phố giáp ranh với tỉnh/thành phố của chi nhánh.
Khách hàng không thuộc 2 trường hợp trên nhưng là doanh nghiệp có thành viên góp vốn chiếm trên 50% vốn điều lệ và/hoặc nắm quyền chi phối hoạt động kinh doanh, tài chính của doanh nghiệp đang quan hệ tín dụng với chi nhánh.
Đối với khách hàng không thuộc các trường hợp trên, Giám đốc Khối Khách hàng doanh nghiệp/Tổng giám đốc có thể xem xét chấp thuận chi nhánh quan hệ tín dụng trên cơ sở nguyên tắc quy định tại Điều 8.1 (Điều 8.3).
Như vậy, căn cứ vào các quy định trên, chi nhánh có thể cấp tín dụng cho khách hàng không cùng địa bàn với chi nhánh trong một số trường hợp nhất định, chứ không hoàn toàn bị hạn chế.

Bạn có cần thêm chi tiết nào về vấn đề liên quan không?

User: Khách hàng là Công ty A mới thành lập để nghị Chi nhánh NHCT cấp GHTD 500 tỷ để thực hiện dự án. Tuy nhiên GHTF này không có bảo đảm bằng tài sản. Chi nhánh có được cấp không?
Assistant: Dựa trên các thông tin từ tài liệu được cung cấp, trường hợp Công ty A là khách hàng mới thành lập và đề nghị cấp GHTD 500 tỷ để thực hiện dự án mà không có tài sản bảo đảm thì Chi nhánh NHCT vẫn có thể cấp GHTD với một số điều kiện nhất định như sau:

Công ty A phải đáp ứng các điều kiện cấp GHTD theo quy định trong "Quy định cụ thể chính sách cấp và quản lý GHTD đối với phân khúc khách hàng doanh nghiệp và ĐCTC phi TCTD" của NHCT.

Mặc dù không có tài sản bảo đảm, nhưng NHCT có thể xem xét cho vay nếu Công ty A đáp ứng điều kiện: a) Nhu cầu vay vốn để sử dụng vào mục đích hợp pháp; và b) Phương án sử dụng vốn khả thi.

Trường hợp Công ty A mới thành lập và có dự án mới triển khai, đi vào hoạt động chưa quá 3 năm thì điều kiện về kết quả kinh doanh lỗ theo kế hoạch có thể không áp dụng. Tuy nhiên, vốn chủ sở hữu của Công ty A vẫn phải lớn hơn 0.

Thông tin trên được nêu tại tài liệu...

Vui lòng cho biết nếu bạn cần thêm thông tin gì về vấn đề này.
</example>

Here is the context:
<context>
{}
</context>

Here is the previous questions of user:
<previous question>
{}
</previous question>

Here is the user's question:
<question>
{}
</question>

Assistant:
"""

## Setup connection with Bedrock
# Setup connection
bedrock_config = Config(
    connect_timeout = 120,
    read_timeout = 120,
    retries = {
        "max_attempts": 1
    },
    region_name = region
)

# Initiate bedrock session
bedrock_client = boto3.client("bedrock-runtime", config = bedrock_config)
bedrock_agent_client = boto3.client(
    "bedrock-agent-runtime",
    config = bedrock_config
) 

# Set usernames and passwords
with open("./config.yaml") as file:
    config = yaml.load(file, Loader = SafeLoader)

# Authenticator screen
authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookies"]["name"],
    config["cookies"]["key"],
    config["cookies"]["expiry_days"],
    config["pre-authorized"]
)

# Hash password
hased_passwords = Hasher(["vietinbanktuyetvoi","vietinbanklanhat"]).generate()

name, authentication_status, username = authenticator.login(
    location = "main",
    max_concurrent_users = 1,
    max_login_attempts = 3
)

# Login for Vietin
if authentication_status == True:
    # Logout
    authenticator.logout()
    
    # Setup input chat
    st.image("Logo_Vietinbank.png")
    st.header("VTB GenAI - Elearning and Credit Policy")
    st.markdown(
        "Xin chào, tôi là Chatbot của VTB. Tôi đã đọc qua các tài liệu về elearning và một số chính sách tín dụng của VTB. Hãy hỏi tôi bất kì thứ gì, nếu tài liệu có đề cập đến, tôi sẽ tìm tài liệu liên quan và trả lời giúp bạn."
    )
    
    # Setup sidebar
    with st.sidebar:
        # Config number of contexts
        numberOfResults = st.number_input(
            "Number of Contexts (recommend 1 - 3)",
            min_value = 1,
            max_value = 20,
            value = 5,
            step = 1,
            placeholder = "Enter number of contexts"
        )
        
        # config number of max tokens
        max_tokens = st.slider(
            "Maximum tokens",
            min_value = 1024,
            max_value = 4096,
            value = 4096,
            step = 1
        )
        
        # Config temperature
        temperature = st.slider(
            "Temperature",
            min_value = 0.00,
            max_value = 1.00,
            value = 0.3,
            step = 0.01
        )
        
        # Config top_p
        top_p = st.slider(
            "Top P",
            min_value = 0.000,
            max_value = 1.000,
            value = 0.000,
            step = 0.001
        )
        
        # Config Top K
        top_k = st.slider(
            "Top K",
            min_value = 0,
            max_value = 500,
            value = 50,
            step = 1
        )
        
        # Config search type
        overrideSearchType = st.selectbox(
            "Search Strategies for LLMs",
            options = ("HYBRID", "SEMANTIC")
        )
    
    ## Setup chat function
    # Initiate session
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.recents = []
    
    # Display chat message from history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    if query := st.chat_input("Hãy hỏi tôi bất cứ thứ gì"):
        # Add user messages to chat history
        st.session_state.messages.append(
            {
                "role": "user",
                "content": query
            }
        )
        
        st.session_state.recents.append(query)
        
        # Display user message
        with st.chat_message(name = "user"):
            st.markdown(query)
            
        # Obtain chat bot messages
        with st.chat_message(name = "assistant"):
            # Semantic search around user input
            retrieval_results = retrieve_context(
                bedrock_agent_client = bedrock_agent_client,
                query = query,
                kbId = kbId,
                numberOfResults = numberOfResults,
                overrideSearchType= overrideSearchType
            )
            
            # Retrieve contexts and sources
            contexts, sources = get_contexts(retrieval_results)
            
            # Input into recent questions
            if "recents" in st.session_state:
                if len(st.session_state.recents) <= 5:
                    recent_questions = st.session_state.recents
                    prompt = prompt.format(
                        contexts, recent_questions, query
                    )
                else:
                    recent_questions = st.session_state.recents[-5:]
                    prompt = prompt.format(
                        contexts, recent_questions, query
                    )
                    
            # Setup payload
            payload = get_payload(
                prompt,
                contexts,
                query,
                max_tokens = max_tokens,
                temperature = temperature,
                top_k = top_k,
                top_p = top_p
            )
            
            # Obtain and stream response:
            response = st.write_stream(stream_data(
                payload = payload,
                modelId = modelId
            ))
            
            # Get desinated URLs of documents
            presigned_uris = generate_presigned_urls(
                sources,
                expiration = 3600
            )
            
            # Get the file name
            file_names = get_file_name(sources)
            
            # Append response to messages
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": response
                }
            )
    
        # Input source of document
        with st.status("Nguồn dữ liệu"):
            for i in range(len(presigned_uris)):
                st.link_button(file_names[i], presigned_uris[i])
elif authentication_status == False:
    st.error("Username/password is not correct")
elif authentication_status == None:
    st.warning("Please enter your username and password")


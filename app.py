from flask import Flask, render_template, request
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import CharacterTextSplitter
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Initialize LLM and Embeddings from OpenAI
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found. Make sure your .env file is named correctly and contains the key.")

llm = ChatOpenAI(
    model="gpt-4",
    temperature=0.7,
    api_key=api_key
)
embeddings = OpenAIEmbeddings()

# Load email templates or use fallback default
def load_email_templates():
    try:
        with open("email_templates.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        print("Warning: email_templates.txt not found. Using default templates.")
        return """
Formal Business Inquiry:
Subject: Business Inquiry from [Your Name]
Dear [Recipient Name],
I hope this message finds you well. I am writing to inquire about [specific topic]. 
Could you please provide more information regarding [specific question]?
Thank you for your time and consideration.
Best regards,
[Your Name]

Job Application:
Subject: Application for [Position Name] - [Your Name]
Dear Hiring Manager,
I am writing to express my interest in the [Position Name] position at [Company Name]. 
With my experience in [relevant experience], I believe I would be a strong candidate for this role.
Please find my resume attached for your review.
Sincerely,
[Your Name]

Informal Business Inquiry:
Subject: Quick Question about [Specific Topic]
Hey [Recipient Name],
Hope you're doing well! I wanted to ask about [specific topic or query]. Could you give me a bit more info on that?
Thanks a bunch!
Best,
[Your Name]

Informal Job Application:
Subject: Application for [Position Name] - Let's Connect!
Hey [Hiring Manager's Name],
I'm really excited about the [Position Name] role at [Company Name]. I think my background in [relevant experience] would be a great fit. I've attached my resume for you.
Looking forward to chatting more!
Cheers,
[Your Name]
"""

# Create vector store from template chunks
def create_vector_store():
    templates = load_email_templates()
    text_splitter = CharacterTextSplitter(
        separator="\n\n",
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )
    chunks = text_splitter.split_text(templates)
    return FAISS.from_texts(chunks, embedding=embeddings)

# Initialize vector store and retriever
vector_store = create_vector_store()
retriever = vector_store.as_retriever(search_kwargs={"k": 3})

# Prompt template for the LLM
email_prompt = PromptTemplate(
    input_variables=["context", "prompt", "recipient", "tone", "length"],
    template="""
You are a professional email assistant. Use the following email templates as reference:
{context}

Generate an email based on the following request:
{prompt}

Recipient: {recipient}
Tone of the email: {tone}
Length of the email: {length}

Structure your response as follows:

Subject: [Email Subject Here]

Body:
[Email Body Here]

Important:
- Include appropriate greeting and closing
- Use proper tone mentioned in the tone of the email and proper formatting
- Personalize for the recipient
- Keep in mind the length of the email
"""
)

# LLM chain for generating email
email_chain = LLMChain(llm=llm, prompt=email_prompt)

# Flask route
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        prompt_text = request.form.get('prompt')
        recipient = request.form.get('recipient')
        tone = request.form.get('tone')
        length = request.form.get('length')

        try:
            # Retrieve relevant templates
            relevant_templates = retriever.get_relevant_documents(prompt_text)
            context = "\n\n".join([doc.page_content for doc in relevant_templates])

            # Generate email
            result = email_chain.run(
                context=context,
                prompt=prompt_text,
                recipient=recipient,
                tone=tone,
                length=length
            )

            # Extract subject and body
            subject = result.split("Subject:")[1].split("\n")[0].strip()
            body = result.split("Body:")[1].strip()

            return render_template('index.html', email_subject=subject, email_body=body)

        except Exception as e:
            error = f"Error generating email: {str(e)}"
            return render_template('index.html', error_message=error)

    return render_template('index.html')

# Run the Flask app
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

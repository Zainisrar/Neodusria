from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
import os
from fastapi import APIRouter, HTTPException
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from PyPDF2 import PdfReader
from langchain_core.documents import Document
from PIL import Image
from fastapi.responses import JSONResponse
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_community.document_loaders import UnstructuredExcelLoader
from langchain_community.document_loaders import UnstructuredPowerPointLoader
from langchain_community.document_loaders import Docx2txtLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.document_loaders import PyMuPDFLoader
from langchain.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import io
import tempfile
from langchain.callbacks import AsyncIteratorCallbackHandler
from fastapi.responses import StreamingResponse
import asyncio
import shutil
from typing import Optional, List
import logging
import json
from fastapi import FastAPI, File, UploadFile, HTTPException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



router = APIRouter(prefix="/chatbot", tags=["chatbot Intelligence"])

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DOCUMENT_PATH = r"D:\office projects\neodustria\app\chatbot.pdf"  # Default document path

# Set environment variable
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Global variables to store the conversation chain
conversation_instance = None
vector_store = None

# Pydantic models for request/response
class QuestionRequest(BaseModel):
    question: str

class QuestionResponse(BaseModel):
    answer: str
    success: bool
    message: Optional[str] = None

class InitResponse(BaseModel):
    success: bool
    message: str
    document_chunks: Optional[int] = None

# Initialize OpenAI client and embeddings
client = OpenAI(api_key=OPENAI_API_KEY)
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

def get_vector_store(text_chunks: List[str]):
    """Create vector store from text chunks"""
    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        vectorstore = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
        return vectorstore
    except Exception as e:
        logger.error(f"Error creating vector store: {str(e)}")
        raise e

def create_conversation_chain(vectorstore, streaming=False, callback=None):
    """Create conversational retrieval chain with optional streaming"""
    try:
        # Configure callbacks properly
        callbacks = [callback] if callback else []
        
        llm = ChatOpenAI(
            model="gpt-4",
            temperature=0,
            streaming=streaming,
            callbacks=callbacks
        )

        memory = ConversationBufferMemory(
            memory_key="chat_history", 
            return_messages=True,
            output_key='answer'
        )

        prompt_template = """
        You are Green, a helpful AI assistant for the company. Use the provided context to answer the user's questions as accurately as possible.
        If the answer is not in the context, admit that you do not know instead of making up an answer.

        Context:
        {context}

        Chat History:
        {chat_history}

        User's Question:
        {question}

        Your Answer:
        """
        prompt = PromptTemplate(
            input_variables=["context", "chat_history", "question"],
            template=prompt_template
        )

        conversation_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 10}),
            memory=memory,
            combine_docs_chain_kwargs={"prompt": prompt},
            return_source_documents=False,
            verbose=False
        )
        return conversation_chain
    except Exception as e:
        logger.error(f"Error creating conversation chain: {str(e)}")
        raise e

def split_documents(pages: List[Document]) -> List[str]:
    """Split documents into chunks"""
    try:
        text_splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        split_docs = text_splitter.split_documents(pages)
        texts = [doc.page_content for doc in split_docs]
        return texts
    except Exception as e:
        logger.error(f"Error splitting documents: {str(e)}")
        raise e

def extract_text_from_pdf(file_path: str) -> List[str]:
    """Extract text from PDF file"""
    try:
        loader = PyMuPDFLoader(file_path)
        pages = loader.load()
        split_docs = split_documents(pages)
        return split_docs
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise e

def process_file(file_path: str) -> List[str]:
    """Process different file types"""
    try:
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.pdf':
            return extract_text_from_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise e

@router.on_event("startup")
async def startup_event():
    """Initialize the conversation chain on startup"""
    global conversation_instance, vector_store
    
    try:
        logger.info("Initializing document processing...")
        
        # Check if default document exists
        if os.path.exists(DOCUMENT_PATH):
            texts = process_file(DOCUMENT_PATH)
            vector_store = get_vector_store(texts)
            conversation_instance = create_conversation_chain(vector_store)
            logger.info(f"Successfully initialized with {len(texts)} text chunks from {DOCUMENT_PATH}")
        else:
            logger.warning(f"Default document {DOCUMENT_PATH} not found. Service will be available for file uploads.")
            
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")


# Alternative streaming implementation using direct LLM streaming
@router.post("/ask/stream-direct")
async def ask_question_stream_direct(request: QuestionRequest):
    """Direct streaming using LLM without conversation chain"""
    global vector_store

    if not vector_store:
        raise HTTPException(status_code=400, detail="No document has been processed. Please upload a document first.")
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    logger.info(f"Processing direct streaming question: {request.question}")

    async def event_generator():
        try:
            # Get relevant documents
            retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 10})
            docs = await asyncio.to_thread(retriever.get_relevant_documents, request.question)
            
            # Prepare context
            context = "\n".join([doc.page_content for doc in docs])
            
            # Create prompt
            prompt = f"""
            You are Green, a helpful AI assistant. Use the provided context to answer the user's questions as accurately as possible.
            If the answer is not in the context, admit that you do not know instead of making up an answer.

            Context:
            {context}

            User's Question:
            {request.question}

            Your Answer:
            """

            # Stream response from OpenAI directly
            stream = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                stream=True,
                temperature=0
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    token = chunk.choices[0].delta.content
                    yield f"data: {json.dumps({'token': token})}\n\n"
            
            yield f"data: {json.dumps({'type': 'done', 'message': 'Stream completed'})}\n\n"
            
        except Exception as e:
            logger.error(f"Error in direct streaming: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(), 
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@router.get("/")
async def root():
    return {"message": "FastAPI is running! Use /upload to send PDF."}


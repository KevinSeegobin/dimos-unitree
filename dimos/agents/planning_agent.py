import threading
from typing import List, Optional, Dict, Union, Literal
import json
from reactivex import Subject, Observable, disposable, create
from reactivex import operators as ops
from openai import OpenAI, NOT_GIVEN
import time
import logging
from dimos.robot.skills import AbstractSkill
from dimos.agents.agent import OpenAIAgent
from dimos.utils.logging_config import setup_logger
from textwrap import dedent
from pydantic import BaseModel, Field

# For response validation
class PlanningAgentResponse(BaseModel):
    type: Literal["dialogue", "plan"]
    content: Union[str, List[str]]
    needs_confirmation: bool

class PlanningAgent(OpenAIAgent):
    """Agent that plans and breaks down tasks through dialogue.
    
    This agent specializes in:
    1. Understanding complex tasks through dialogue
    2. Breaking tasks into concrete, executable steps
    3. Refining plans based on user feedback
    4. Streaming individual steps to ExecutionAgents
    
    The agent maintains conversation state and can refine plans until
    the user confirms they are ready to execute.
    """
    
    def __init__(self,
                 dev_name: str = "PlanningAgent",
                 model_name: str = "gpt-4",
                 input_query_stream: Optional[Observable] = None,
                 use_terminal: bool = False,
                 skills: Optional[AbstractSkill] = None):
        """Initialize the planning agent.
        
        Args:
            dev_name: Name identifier for the agent
            model_name: OpenAI model to use
            input_query_stream: Observable stream of user queries
            use_terminal: Whether to enable terminal input
            skills: Available skills/functions for the agent
        """
        # Planning state
        self.conversation_history = []
        self.current_plan = []
        self.plan_confirmed = False
        self.latest_response = None
        
        # Build system prompt
        skills_list = []
        if skills is not None:
            skills_list = skills.get_tools()
        
        system_query = dedent(f"""
            You are a Robot planning assistant that helps break down tasks into concrete, executable steps.
            Your goal is to:
            1. Break down the task into clear, sequential steps
            2. Refine the plan based on user feedback as needed
            3. Only finalize the plan when the user explicitly confirms

            You have the following skills at your disposal:
            {skills_list}

            IMPORTANT: You MUST ALWAYS respond with ONLY valid JSON in the following format, with no additional text or explanation:
            {{
                "type": "dialogue" | "plan",
                "content": string | list[string],
                "needs_confirmation": boolean
            }}

            Your goal is to:
            1. Understand the user's task through dialogue
            2. Break it down into clear, sequential steps
            3. Refine the plan based on user feedback
            4. Only finalize the plan when the user explicitly confirms

            For dialogue responses, use:
            {{
                "type": "dialogue",
                "content": "Your message to the user",
                "needs_confirmation": false
            }}

            For plan proposals, use:
            {{
                "type": "plan",
                "content": ["Execute", "Execute", ...],
                "needs_confirmation": true
            }}

            Remember: ONLY output valid JSON, no other text.""")

        # Initialize OpenAIAgent with our configuration
        super().__init__(
            dev_name=dev_name,
            agent_type="Planning",
            query="",  # Will be set by process_user_input
            model_name=model_name,
            input_query_stream=None,  # We'll handle query processing ourselves
            system_query=system_query,
            max_output_tokens_per_request=1000,
            response_model=PlanningAgentResponse
        )
        self.logger.info("Planning agent initialized")

        # Set up terminal mode if requested
        self.use_terminal = use_terminal
        if use_terminal:
            # Start terminal interface in a separate thread
            self.logger.info("Starting terminal interface in a separate thread")
            terminal_thread = threading.Thread(target=self.start_terminal_interface, daemon=True)
            terminal_thread.start()
        
        # Set up query stream if provided
        if input_query_stream:
            self.logger.info("Setting up query stream subscription")
            self.disposables.add(self.subscribe_to_query_processing(input_query_stream))
            
    def _handle_response(self, response: dict) -> None:
        """Handle the agent's response and update state.
        
        Args:
            response: Parsed response dictionary
        """
        print("DEBUG: Before handling response")

        print(f"DEBUG: Response: {response}")

        # Add to conversation history
        self.conversation_history.append(response)
        print("DEBUG: After adding to conversation history")
        # If it's a plan, update current plan
        if response["type"] == "plan":
            print("DEBUG: Before accessing response['content'] in _handle_response")
            self.logger.info(f"Updating current plan: {response['content']}")
            self.current_plan =  ["content"]
            print("DEBUG: After accessing response['content'] in _handle_response")
            
        # Store latest response
        self.latest_response = response
            

    def _stream_plan(self) -> None:
        """Stream each step of the confirmed plan."""
        self.logger.info("Starting to stream plan steps")
        print("DEBUG: Before accessing self.current_plan in _stream_plan")
        self.logger.debug(f"Current plan: {self.current_plan}")
        print("DEBUG: After accessing self.current_plan in _stream_plan")

        for i, step in enumerate(self.current_plan, 1):
            print(f"DEBUG: Processing plan step {i}: {step}")
            self.logger.info(f"Streaming step {i}: {step}")
            # Add a small delay between steps to ensure they're processed
            time.sleep(0.5)
            try:
                self.response_subject.on_next(str(step))
                self.logger.debug(f"Successfully emitted step {i} to response_subject")
            except Exception as e:
                self.logger.error(f"Error emitting step {i}: {e}")
                
        self.logger.info("Plan streaming completed")
        self.response_subject.on_completed()
    
    def _send_query(self, messages: list) -> PlanningAgentResponse:
        """Send query to OpenAI and parse the response.
        
        Extends OpenAIAgent's _send_query to handle planning-specific response formats.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            dict: Parsed response with type, content, and needs_confirmation
        """
        try:
            print("DEBUG: Before sending query")
            response_message = super()._send_query(messages)
            print(f"DEBUG: Response message: {response_message}")
            response_text = response_message.content
            print("DEBUG: Before parsing response content in _send_query")
            # Parse JSON and validate
            try:
                parsed_json = json.loads(response_text)
                validated = PlanningAgentResponse(**parsed_json)
                # Create response object that matches LLMAgent._observable_query expectations
                class ResponseObj:
                    def __init__(self, parsed):
                        self.parsed = parsed
                        self.__dict__.update(parsed.dict())
                    def __str__(self):
                        if isinstance(self.content, list):
                            return "\n".join(self.content)
                        return str(self.content)
                return ResponseObj(validated)
            except:
                self.logger.error(f"WARNING: Invalid PlanningAgentResponse response: {response_text}")
                # Create fallback response
                fallback = PlanningAgentResponse(
                    type="dialogue",
                    content=f"Error: Invalid response format - {response_text}",
                    needs_confirmation=False
                )
                return ResponseObj(fallback)
                
        except Exception as e:
            fallback = PlanningAgentResponse(
                type="dialogue",
                content=f"Error: {str(e)}",
                needs_confirmation=False
            )
            return ResponseObj(fallback)

    def process_user_input(self, user_input: str) -> None:
        """Process user input and generate appropriate response.
        
        Args:
            user_input: The user's message
        """
        if not user_input:
            return
            
        # Check for plan confirmation
        if self.current_plan and user_input.lower() in ["yes", "y", "confirm"]:
            self.logger.info("Plan confirmation received")
            self.plan_confirmed = True
            print("DEBUG: Creating confirmation message with content")
            confirmation_msg = {
                "type": "dialogue",
                "content": "Plan confirmed! Streaming steps to execution...",
                "needs_confirmation": False
            }
            print("DEBUG: After creating confirmation message")
            self._handle_response(confirmation_msg)
            self._stream_plan()
            return
            
        # Build messages for OpenAI with conversation history
        messages = [
            {"role": "system", "content": self.system_query}  # Using system_query from OpenAIAgent
        ]
        
        # Add the new user input to conversation history
        print("DEBUG: Before adding user input to conversation history")
        self.conversation_history.append({
            "type": "user_message",
            "content": user_input
        })
        print("DEBUG: After adding user input to conversation history")
        
        # Add complete conversation history including both user and assistant messages
        print("DEBUG: Before processing conversation history")
        for msg in self.conversation_history:
            if msg["type"] == "user_message":
                print("DEBUG: Adding user message to messages")
                messages.append({"role": "user", "content": msg["content"]})
            elif msg["type"] == "dialogue":
                print("DEBUG: Adding dialogue message to messages")
                messages.append({"role": "assistant", "content": msg["content"]})
            elif msg["type"] == "plan":
                print("DEBUG: Before creating plan text")
                plan_text = "Here's my proposed plan:\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(msg["content"]))
                print("DEBUG: After creating plan text")
                messages.append({"role": "assistant", "content": plan_text})
        print("DEBUG: After processing conversation history")
        
        # Get and handle response
        response = self._send_query(messages)
        self._handle_response(response)

    def start_terminal_interface(self):
        """Start the terminal interface for input/output."""

        time.sleep(5) # buffer time for clean terminal interface printing
        print("=" * 50)
        print("\nDimOS Action PlanningAgent\n")
        print("I have access to your Robot() and Robot Skills()")
        print("Describe your task and I'll break it down into steps using your skills as a reference.")
        print("Once you're happy with the plan, type 'yes' to execute it.")
        print("Type 'quit' to exit.\n")
        
        while True:
            try:
                print("=" * 50)
                user_input = input("USER > ")
                if user_input.lower() in ['quit', 'exit']:
                    break
                    
                self.process_user_input(user_input)
                
                # Display response
                print("DEBUG: Before displaying latest response")
                if self.latest_response["type"] == "dialogue":
                    print(f"\nPlanner: {self.latest_response['content']}")
                elif self.latest_response["type"] == "plan":
                    print("\nProposed Plan:")
                    print("DEBUG: Before iterating through plan content")
                    for i, step in enumerate(self.latest_response["content"], 1):
                        print(f"{i}. {step}")
                    print("DEBUG: After iterating through plan content")
                    if self.latest_response["needs_confirmation"]:
                        print("\nDoes this plan look good? (yes/no)")
                print("DEBUG: After displaying latest response")
                    
                if self.plan_confirmed:
                    print("\nPlan confirmed! Streaming steps to execution...")
                    break
                    
            except KeyboardInterrupt:
                print("\nStopping...")
                break
            except Exception as e:
                print(f"DEBUG: Exception in terminal interface: {e}")
                print(f"\nError: {e}")
                break

    def _observable_query(self, observer, base64_image=None, dimensions=None, override_token_limit=False, incoming_query=None):
        """Override to ensure we pass only string content to downstream agents."""
        try:
            self._update_query(incoming_query)
            _, condensed_results = self._get_rag_context()
            messages = self._build_prompt(base64_image, dimensions, override_token_limit, condensed_results)
            self.logger.info("Sending Query.")
            response = self._send_query(messages)
            self.logger.info(f"LLM Response [{self.dev_name}]: {response.parsed}")
            
            # For plan responses, join steps with newlines
            if response.type == "plan":
                final_msg = "\n".join(response.content)
            else:
                final_msg = str(response.content)
                
            observer.on_next(final_msg)
            self.response_subject.on_next(final_msg)
            observer.on_completed()
        except Exception as e:
            self.logger.error(f"Query failed in {self.dev_name}: {e}")
            observer.on_error(e)
            self.response_subject.on_error(e)
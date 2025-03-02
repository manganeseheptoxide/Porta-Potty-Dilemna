from mem0 import Memory
from openai import OpenAI
from pydantic import BaseModel
import streamlit as st
import re
import os

os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

class DayOutput(BaseModel):
    thoughts: str
    response: str

class VoteOutput(BaseModel):
    vote: str
    reason: str

class RecapOutput(BaseModel):
    recap: str

class AI_Player():
    def __init__(self, session_state, name: str, model: str = "gpt-4o-mini"):
        super().__init__()
        self.session_state = session_state # the session_state object in main
        self.name = name
        self.model = model
        self.client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        self.round_thoughts = []    # a combination of thoughts and chatlogs
                                    # basically:
                                    # PLAYER1: blahblah
                                    # PLAYER2: blahblah
                                    # PLAYER3: blahblah
                                    # (THIS_PLAYER_THOUGHTS): what i think about player 1 and the situation is blahblah
                                    # THIS_PLAYER: my response blahblah
        self.active_players = session_state.active_players # keeps track of who is still in the round
        self.round_chatlog = session_state.messages # the chatlog without this player's thoughts
        self.round_recap = [] # recap everytime the round ends
        self.last_chat = None
        self.prompt = session_state.situation
        print(f"Player {self.name} has joined the game!")

    def respond(self):
        # updates internal round chatlog w/ thoughts
        if self.last_chat is None:
            self.round_thoughts += self.round_chatlog
        else:
             # it takes the chats that has been added to the messages since it last responded and adds them into round_thoughts
            self.round_thoughts += self.round_chatlog[self.last_chat:]

        system_messages = [
            {"role": "system", "content": f"Specific instructions: {self.prompt}."},
            {"role": "system", "content": f"Your name in the conversation is {self.name}, your messages/responses are after the *{self.name}: *. Check the chat logs and maintain continuity."},
            {"role": "system", "content": f"The following are still in active in the conversation and is not voted out: {str(list(self.active_players.keys()))}"},
            {"role": "system", "content": f"The logs with '({self.name.upper()}_THOUGHTS)' is your thoughts about the conversation at that moment, the thoughts that you generate are not visible to others but you."},
            {"role": "system", "content": f"Respond to the most recent chat or if you need to respond to refer to a specific person use: @Person_name to tag them"},
            {"role": "system", "content": f"Limit your responses to 200 Characters."},
            {"role": "system", "content": f"For the output format, the 'thoughts' correspond to your thoughts about the conversation and it must be a string. If you dont have any special thoughts about it, put the string 'none'"},
            {"role": "system", "content": f"For the output format, the 'response' correspond to your response to the conversation and it must be a string. If you wish to not respond anymore or want to observe more, put the string 'pass'"},
            {"role": "system", "content": f"Time left for the discussion: {self.session_state.day_timer} seconds. If did not pass, it would take you 1 to 2 seconds to respond."}
            ]
        round_recaps = [{"role": "system", "content": f"The recap for round {i+1}: {self.round_recap[i]}"} for i in range(len(self.round_recap))]
        print(f"{self.session_state.day_timer}")
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=system_messages + round_recaps + self.round_thoughts,
            response_format=DayOutput,
        )
        text = str(response.choices[0].message.parsed.response)

        message = re.sub(r'^[^:]+: ', '', text)
        if message.lower() != 'pass':
            # adds it's chat on the session_state messages
            self.round_chatlog.append({"role": "assistant", "content": f"{self.name}: {message}"})

        self.last_chat = len(self.round_chatlog) # keeps track of it's last chat/thought

        # (THIS_PLAYER_THOUGHTS): what i think about player 1 and the situation is blahblah
        self.round_thoughts.append({"role": "assistant", "content": f"({self.name.upper()}_THOUGHTS) {response.choices[0].message.parsed.thoughts}"})
        # THIS_PLAYER: my response blahblah
        self.round_thoughts.append({"role": "assistant", "content": f"{self.name}: {message}"})
        print(self.round_thoughts)
        return message # can return the string 'pass'
    
    def vote(self, revote: bool = False, tie_break: list = None):

        if self.last_chat is None:
            self.round_thoughts += self.round_chatlog
        else:
            self.round_thoughts += self.round_chatlog[self.last_chat:]
        
        s = dict(self.active_players)
        del s[self.name.lower()]

        if tie_break is not None:
            choices = tie_break
        else:
            # s contains all the valid voting choices which does not include self
            choices = str(list(s.keys()))
        
        print(f"Choices for {self.name}: {choices}")
        tie_break_message = [{"role": "system", "content": f"There was a vote tie! Choose from the following to break the tie: {choices}"}]
        revote_message = [{"role": "system", "content": f"You chose an invalid vote! You can only choose from the following: {choices}"}]
        system_messages = [
            {"role": "system", "content": f"Specific instructions: {self.prompt}."},
            {"role": "system", "content": f"Your name in the conversation is {self.name}, your messages/responses are after the *{self.name}: *. Check the chat logs and maintain continuity."},
            {"role": "system", "content": f"The logs with '({self.name.upper()}_THOUGHTS)' is your thoughts about the conversation at that moment, the thoughts that you generate are not visible to others but you."},
            {"role": "system", "content": f"Based on the conversation and your thoughts, vote for who you think should go first. YOU MUST VOTE SOMEONE ELSE AND NOT YOURSELF UNLESS IT'S A TIE BREAKER AND YOU'RE INCLUDED!"},
            {"role": "system", "content": f"YOU MUST VOTE SOMEONE ELSE. However, if it's a tie-breaker and you are included, you can vote yourself."},
            {"role": "system", "content": f"For the output format, the 'vote' must contain the person's NAME of who you will vote for. You can only choose from the following: {choices}"},
            {"role": "system", "content": f"For the output format, the 'reason' correspond to your reason behind your vote."}
            ] 
        round_recaps = [{"role": "system", "content": f"The recap for round {i+1}: {self.round_recap[i]}"} for i in range(len(self.round_recap))]
        messages = system_messages + round_recaps + self.round_thoughts
        
        if revote:
            messages += revote_message
        if tie_break is not None:
            messages += tie_break_message
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=VoteOutput,
        )

        vote = response.choices[0].message.parsed.vote
        text = str(response.choices[0].message.parsed.reason)
        reason = re.sub(r'^[^:]+: ', '', text)
        vote_reason = f"I voted for {vote} because {reason}"

        if vote in list(s.keys()): # valid vote, not tie breaker
            self.round_thoughts.append({"role": "assistant", "content": f"({self.name.upper()}_VOTE) {vote_reason}"})
            return response.choices[0].message.parsed.vote.upper()
        elif tie_break is not None and vote in tie_break: # valid vote, tie breaker
            self.round_thoughts.append({"role": "assistant", "content": f"({self.name.upper()}_VOTE) {vote_reason}"})
            return response.choices[0].message.parsed.vote.upper()
        elif tie_break is not None and vote not in tie_break: # not valid vote, tie breaker
            return self.vote(revote=True, tie_break = tie_break)
        else: # not valid vote
            return self.vote(revote=True)
    
    def think(self):
        if self.last_chat is None:
            self.round_thoughts += self.round_chatlog
        else:
            self.round_thoughts += self.round_chatlog[self.last_chat:]

        # insert thinking process here

        self.last_chat = len(self.round_chatlog)


    def recap(self):

        if self.last_chat is None:
            self.round_thoughts += self.round_chatlog
        else:
            self.round_thoughts += self.round_chatlog[self.last_chat:]

        system_messages = [
            {"role": "system", "content": f"Specific instructions: {self.prompt}."},
            {"role": "system", "content": f"Your name in the conversation is {self.name}, your messages/responses are after the *{self.name}: *. Check the chat logs and maintain continuity."},
            {"role": "system", "content": f"The logs with '({self.name.upper()}_THOUGHTS)' is your thoughts about the conversation at that moment, the thoughts that you generate are not visible to others but you."},
            {"role": "system", "content": f"Your task is to create a recap what happened last round based on your account. You will use this as a future reference. Take note of who was voted out"},
            {"role": "system", "content": f"For the output format, the 'recap' correspond to your recap about the last round and it must be a string."},
            {"role": "system", "content": f"Do not forget who got voted out in this round!"},
            ] 
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=system_messages + self.round_thoughts,
            response_format=RecapOutput,
        )
        recap = str(response.choices[0].message.parsed.recap)
        self.round_recap.append(recap)
        # print(recap)

    def new_round(self):
        # mimics the clearing of the chatbox
        self.round_thoughts = []
        self.last_chat = None
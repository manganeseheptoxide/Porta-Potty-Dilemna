import streamlit as st
from openai import OpenAI
from itertools import cycle

from ai_agents import AI_Player

player_names = ["John", "Rob", "Bobby", "Khalid", "Yu"]
# player_names = ["John", "Mike", "Rob", "Bobby"]

st.title("Porta Potty Dilemna!")
if "situation" not in st.session_state: # REQUIRED
    st.session_state.situation = "There are many of you are outside the men's bathroom and there was no definitive queue line. Your bladder is almost going to explode. You must convince others on why you should go first. During the DISCUSSION phase, you can only discuss and convince other people, only during the VOTING phase you can vote."
if "messages" not in st.session_state: # REQUIRED
    st.session_state.messages = []
if "day_timer" not in st.session_state:
    st.session_state.day_timer = -999
if "active_players" not in st.session_state: # REQUIRED
    st.session_state.active_players = {name.lower(): "active" for name in player_names}
if "players" not in st.session_state:
    st.session_state.players = {name.lower() : AI_Player(name=name, session_state=st.session_state) for name in player_names}
    # st.session_state.active_players = {name.lower(): "active" for name in player_names}
if "queue" not in st.session_state:
    st.session_state.queue = cycle(st.session_state.players.keys()) # order of players to respond

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"]) # prints the chat

if prompt := st.chat_input("Type anything and enter to start."):

    st.session_state.messages.append({"role":"user", "content": f"Phase: DISCUSSION"}) # added to chatlogs
    while len(st.session_state.players) > 2: # while more than 2 players remain
        st.session_state.day_timer = 15
        passed = 0
        # TALKING ROUND
        while st.session_state.day_timer > 0 and passed < len(st.session_state.active_players) - 1:
            # keeps going until all players passed or when time is out
            player_turn = next(st.session_state.queue)
            with st.chat_message("assistant"):
                typing_placeholder = st.empty()
                typing_placeholder.markdown(f"**{st.session_state.players[player_turn].name} is typing...**")
                response = st.session_state.players[player_turn].respond()
                if response.lower() == 'pass':
                    passed += 1
                    typing_placeholder.markdown(f"**{st.session_state.players[player_turn].name} passed.**")
                else:
                    passed = 0
                    typing_placeholder.markdown(f"{st.session_state.players[player_turn].name}: {response}")
        # VOTING ROUND
        players = list(st.session_state.active_players.keys())
        player_vote = {name.lower() : 0 for name in players}
        
        st.session_state.messages.append({"role":"user", "content": f"Phase: VOTING"}) # added to chatlogs
        most_voted = []
        voted = False
        while len(most_voted) != 1 or not voted: # while vote is not unanimous
            if voted: # tie 
                names = ""
                for i in range(len(most_voted) - 1):
                    names += f"{most_voted[i].capitalize()}, "
                names += f"and {most_voted[len(most_voted) - 1].capitalize()}"
                tie_message = f"**Votes are tied for {names}! Only one can go!**"
                with st.chat_message("user"):
                    st.markdown(tie_message)
                st.session_state.messages.append({"role":"user", "content": f"{tie_message}"}) # added to chatlogs
                for _ in range(len(st.session_state.players)):
                    player_turn = next(st.session_state.queue)
                    vote = st.session_state.players[player_turn].vote(tie_break=most_voted)
                    if vote.lower() != 'pass':
                        with st.chat_message("assistant"):
                            vote_alert = f"{st.session_state.players[player_turn].name} voted for {vote.capitalize()}."
                            st.markdown(vote_alert)
                        player_vote[vote.lower()] += 1
                        st.session_state.messages.append({"role":"user", "content": f"{vote_alert}"}) # added to chatlogs
                highest_vote = max(player_vote.values())
                most_voted = [key for key, value in player_vote.items() if value == highest_vote]
            else: # first time everyone will vote
                for _ in range(len(st.session_state.players)):
                    player_turn = next(st.session_state.queue)
                    vote = st.session_state.players[player_turn].vote()
                    if vote.lower() != 'pass':
                        with st.chat_message("assistant"):
                            vote_alert = f"{st.session_state.players[player_turn].name} voted for {vote.capitalize()}."
                            st.markdown(vote_alert)
                        player_vote[vote.lower()] += 1
                        st.session_state.messages.append({"role":"user", "content": f"{vote_alert}"}) # added to chatlogs
                highest_vote = max(player_vote.values())
                most_voted = [key for key, value in player_vote.items() if value == highest_vote]
            voted = True

        print(most_voted[0])
        vote_message = f"{most_voted[0].capitalize()} has been voted to go next. Continue the discussion to decide who needs to go next!"
        with st.chat_message("user"):
            st.markdown(f"**{vote_message}**")
        st.session_state.messages.append({"role":"user", "content": f"{vote_message}"}) # added to chatlogs

        # END ROUND
        del st.session_state.active_players[most_voted[0]]
        del st.session_state.players[most_voted[0]]
        st.session_state.queue = cycle(st.session_state.players.keys())
        st.session_state.messages[:] = st.session_state.messages[:1]
        for _ in range(len(st.session_state.players)):
            # make players recap 
            player_turn = next(st.session_state.queue)
            st.session_state.players[player_turn].recap()
            st.session_state.players[player_turn].new_round()

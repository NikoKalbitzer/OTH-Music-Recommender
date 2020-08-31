import os
import time
import tekore as tk
import json
import re

import config_project
import mpd_connector


class TagExtractor:
    """
    This class calls the spotify api to get high-level descriptors for the songs of the in the config file specifed MPD Server.
    These descriptors are serialized to a json file along with "artist","title", "popularity", "genre","album" and"date".
    The top 3 related artists for every artist in the mpd media library are stored to a 2nd JSON file.
    Instantiate this class to call the above mentioned functionality.
    """
    def __init__(self):
        print("Extracting tags from Spotify")
        self.spotify = self.init_spotify()
        song_list = mpd_connector.MpdConnector(config_project.MPD_IP, config_project.MPD_PORT).get_all_songs()
        id_name_list = self.get_spotify_data(song_list)
        self.get_similiar_artists(id_name_list)
        list_with_high_level_tags = self.match_high_level_tags(id_name_list)
        self.save_as_json(list_with_high_level_tags, config_project.PATH_SONG_DATA)
        print("Finished extracting Tags.")

    def init_spotify(self):
        """
        Initialize + authorize
        :return: spotify object on which api methods can be called
        """
        cred = tk.RefreshingCredentials(config_project.CLIENT_ID, config_project.CLIENT_SECRET, config_project.REDIRECT_URI)
        # app_token = cred.request_client_token()
        user_token = cred.refresh_user_token(config_project.REFRESH_TOKEN)
        sender = tk.RetryingSender(sender=tk.CachingSender())
        spotify = tk.Spotify(user_token, max_limits_on=True, sender=sender)
        return spotify

    def get_spotify_data(self, songnames_dict):
        """
        Getting the spotify ids by searching for artists and songnames parsed from the mpd tags
        :param songnames_dict:
        :param spotify:
        :return:
        """
        songnames_dict = self._remove_brackets(songnames_dict)
        spotify_id_list = []
        error_list = []
        for single_track_info in songnames_dict:
            try:  # to catch all api exceptions
                track_paging_object, = self.spotify.search(
                    single_track_info["title"] + " " + single_track_info["artist"], limit=1)
                if len(track_paging_object.items) != 0:
                    spotify_id_list.append({"artist": single_track_info["artist"], "title": single_track_info["title"],
                                            "popularity": track_paging_object.items[0].popularity,
                                            "id": track_paging_object.items[0].id, "genre": single_track_info["genre"],
                                            "album": single_track_info["album"], "date": single_track_info["date"],
                                            "artist_id": track_paging_object.items[0].artists[0].id})
                else:
                    error_list.append(single_track_info)
            except Exception as e:
                print(e)
                time.sleep(1)
                print("wait 1s, api exception")
                error_list.append(single_track_info)
        print("Found on Spotify:", len(spotify_id_list), "/", len(songnames_dict))
        print("Songs not found:", *error_list)
        return spotify_id_list

    def _remove_brackets(self, dict_list):
        """
        remove the brackets from song and artist names, to increase the chance of a match on spotify
        :param dict_list:
        :return:
        """
        for song in dict_list:
            song["title"] = re.sub("\((.*?)\)", "", song["title"]).strip()
            song["artist"] = re.sub("\((.*?)\)", "", song["artist"]).strip()
        return dict_list

    def get_similiar_artists(self, spotify_data):
        artist_dict = {}
        for song_info in spotify_data:
            related_artists = self.spotify.artist_related_artists(song_info["artist_id"])
            artists_realted = []
            for i in range(0, 3):  # just append the first 3 related artists
                artists_realted.append(related_artists[i].name)
            artist_dict[song_info["artist"]] = artists_realted
        self.save_as_json(artist_dict, config_project.PATH_RELATED_ARTISTS)
        return artist_dict

    def match_high_level_tags(self, id_name_list):
        """
        :param id_name_list: from get_spotify_data
        :return: list of dict
        """
        for song_info in id_name_list:
            audio_features = self.spotify.track_audio_features(song_info["id"])
            reduced_audio_features = AudioFeatures(audio_features.valence, audio_features.danceability,
                                                   audio_features.energy, self._scale_tempo_down(audio_features.tempo),
                                                   audio_features.acousticness,
                                                   audio_features.speechiness)
            song_info["audio_features"] = reduced_audio_features.asdict()
            song_info.pop("id", None)
            song_info.pop("artist_id", None)
        return id_name_list

    def _scale_tempo_down(self, tempo_in_bpm):
        """
        Scale Tempo attribute down to a scale from 0 - 1. Max BPM (Beats per minute) is assumed to be 225, since its extremely
        rare for a song to have a higher BPM
        """
        max_bpm = 225
        if tempo_in_bpm > max_bpm:
            tempo_in_bpm = max_bpm
        return round(tempo_in_bpm / max_bpm, 3)

    def save_as_json(self, high_level_dict_list, save_path):
        with open(save_path, "w") as file_name:
            json.dump(high_level_dict_list, file_name, indent=4)


class AudioFeatures:
    def __init__(self, valence, danceability, energy, tempo, acousticness, speechiness):
        self.valence = valence
        self.danceability = danceability
        self.energy = energy
        self.tempo = tempo
        self.acousticness = acousticness
        self.speechiness = speechiness

    def asdict(self):
        return {"valence": self.valence, "danceability": self.danceability, "energy": self.energy, "tempo": self.tempo,
                "acousticness": self.acousticness, "speechiness": self.speechiness}
"""Podcast source modules for Clawler."""
from clawler.sources.podcasts.base import PodcastBaseSource
from clawler.sources.podcasts.apple import ApplePodcastsSource
from clawler.sources.podcasts.spotify import SpotifyPodcastSource
from clawler.sources.podcasts.youtube import YouTubePodcastSource
from clawler.sources.podcasts.rss import PodcastRSSSource

__all__ = [
    "PodcastBaseSource",
    "ApplePodcastsSource",
    "SpotifyPodcastSource",
    "YouTubePodcastSource",
    "PodcastRSSSource",
]

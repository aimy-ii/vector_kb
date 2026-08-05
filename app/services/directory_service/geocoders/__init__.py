"""Выбор геокодера. Меняется здесь и больше нигде."""

from app.services.directory_service.geocoders.nominatim import NominatimGeocoder

geocoder = NominatimGeocoder()

__all__ = ["NominatimGeocoder", "geocoder"]

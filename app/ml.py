"""Machine learning functions"""
import requests
from bs4 import BeautifulSoup as bs
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.state_abbr import us_state_abbrev as abbr
from pathlib import Path
import pandas as pd
from pypika import Query, Table
import asyncio
from app.db import database


# conn = get_db()


router = APIRouter()


class City(BaseModel):
    city: str
    state: str


class CityData(BaseModel):
    city: City
    latitude: float
    longitude: float
    rental_price: float
    crime: str
    pollution: str
    walkability: float
    livability: float


def validate_city(
    city: City,
) -> City:
    city.city = city.city.title()

    try:
        if len(city.state) > 2:
            city.state = city.state.title()
            city.state = abbr[city.state]
        else:
            city.state = city.state.upper()
    except KeyError:
        raise HTTPException(status_code=422, detail=f"Unknown state: '{city.state}'")

    return city


@router.post("/api/get_data", response_model=CityData)
async def get_data(city: City):
    city = validate_city(city)

    tasks = await asyncio.gather(
        get_coordinates(city),
        get_crime(city),
        get_walkability(city),
        get_pollution(city),
        get_rental_price(city),
        get_livability(city),
    )

    data = {"city": city}

    for t in tasks:
        data.update(t)
    
    print(data)

    return data


@router.post("/api/coordinates")
async def get_coordinates(city: City):
    city = validate_city(city)
    data = Table("data")
    q = (
        Query.from_(data)
        .select(data['lat'], data['lon'])
        .where(data.City == city.city)
        .where(data.State == city.state)
    )
    value = await database.fetch_one(str(q))
    return {"latitude": value[0], "longitude": value[1]}


@router.post("/api/crime")
async def get_crime(city: City):
    city = validate_city(city)
    data = Table("data")
    q = (
        Query.from_(data)
        .select(data['Crime Rating'])
        .where(data.City == city.city)
        .where(data.State == city.state)
    )
    value = await database.fetch_one(str(q))
    return {"crime": value[0]}


@router.post("/api/rental_price")
async def get_rental_price(city: City):
    city = validate_city(city)
    data = Table("data")
    q = (
        Query.from_(data)
        .select(data['Rent'])
        .where(data.City == city.city)
        .where(data.State == city.state)
    )
    value = await database.fetch_one(str(q))

    return {"rental_price": value[0]}


@router.post("/api/pollution")
async def get_pollution(city: City):
    city = validate_city(city)
    data = Table("data")
    q = (
        Query.from_(data)
        .select(data['Level of Concern'])
        .where(data.City == city.city)
        .where(data.State == city.state)
    )
    value = await database.fetch_one(str(q))
    return {"pollution": value[0]}


@router.post("/api/walkability")
async def get_walkability(city: City):
    city = validate_city(city)
    try:
        score = (await get_walkscore(**city.dict()))[0]
    except IndexError:
        raise HTTPException(
            status_code=422, detail=f"Walkscore not found for {city.city}, {city.state}"
        )

    return {"walkability": score}


async def get_walkscore(city: str, state: str):
    """Input: City, 2 letter abbreviation for state
    Returns a list containing WalkScore, BusScore, and BikeScore in that order"""

    r = requests.get(f"https://www.walkscore.com/{state}/{city}")
    images = bs(r.text, features="lxml").select(".block-header-badge img")
    return [int(str(x)[10:12]) for x in images]


@router.post("/api/livability")
async def get_livability(city: City):
    return {"livability": 47.0}

@router.post("/api/population")
async def get_population(city: City):
    city = validate_city(city)
    data = Table("data")
    q = (
        Query.from_(data)
        .select(data['Population'])
        .where(data.City == city.city)
        .where(data.State == city.state)
    )
    value = await database.fetch_one(str(q))
    return {"Population": value[0]}
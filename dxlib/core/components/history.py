from __future__ import annotations

import enum
from dataclasses import dataclass
from functools import reduce
from typing import List, Dict

import pandas as pd

from .security import SecurityManager


class HistoryLevel(enum.Enum):
    DATE = "date"
    SECURITY = "security"

    @classmethod
    def levels(cls):
        return list(cls.__members__.values())

    def __dict__(self):
        return self.value


@dataclass
class HistorySchema:
    levels: List[HistoryLevel]
    fields: List[str]
    security_manager: SecurityManager

    def __init__(
            self,
            levels: List[HistoryLevel] = None,
            fields: List[str] = None,
            security_manager: SecurityManager = None,
    ):
        self.levels = levels if levels else HistoryLevel.levels()
        self.fields = fields if fields else []
        self.security_manager = security_manager if security_manager else SecurityManager()

    def __dict__(self):
        return {
            "levels": [level.__dict__() for level in self.levels],
            "fields": self.fields,
            "security_manager": self.security_manager.__dict__(),
        }

    @classmethod
    def from_dict(cls, data: dict):
        return HistorySchema(**data)


class HistoryConstructor:
    def __init__(self):
        self.schema = HistorySchema()

    def from_dict(self, history: dict):
        return History(history, self.schema)

    def from_tuple(self, history: tuple):
        return History.from_tuple(history, self.schema)

    def update_schema(self, securities: List[str] = None, fields: List[str] = None):
        if securities is None:
            securities = self.schema.security_manager
        if fields is None:
            fields = self.schema.fields

        self.schema.security_manager.add_list(securities)
        self.schema.fields += fields

    def update_df(self, df: pd.DataFrame):
        df.index = pd.MultiIndex.from_tuples(
            df.index, names=[level.value for level in self.schema.levels]
        )
        if HistoryLevel.SECURITY in self.schema.levels:
            df.index = df.index.set_levels(
                [self.schema.security_manager.get(security) for security in df.index.levels[1]],
                level=HistoryLevel.SECURITY.value
            )
        return df

    def __call__(self, df: pd.DataFrame | dict | None = None, schema: HistorySchema | None = None):
        if df is None:
            df = pd.DataFrame()
        elif isinstance(df, dict):
            df = pd.DataFrame.from_dict(df, orient="index")
        elif not isinstance(df, pd.DataFrame):
            raise ValueError(f"Invalid type {type(df)} for df")

        if schema is None:
            schema = HistorySchema.from_dict({})
        elif not isinstance(schema, HistorySchema):
            raise ValueError(f"Invalid type {type(schema)} for schema")

        df.index = pd.MultiIndex.from_tuples(
            df.index, names=[level.value for level in schema.levels]
        )

        self.schema = schema
        self.update_schema()
        self.update_df(df)

        return History(df, self.schema)


class History:
    def __init__(
            self,
            df: pd.DataFrame | dict | None = None,
            schema: HistorySchema | None = None,
    ):
        """
        History is a multi-indexed dataframe encapsulation
        with dates and securities as the index and bar fields as the columns.

        Args:
            df: pandas DataFrame or dict with multi-index and bar fields as columns

        """
        if df is None:
            df = pd.DataFrame()
        elif isinstance(df, dict):
            df = pd.DataFrame.from_dict(df, orient="index")
        elif not isinstance(df, pd.DataFrame):
            raise ValueError(f"Invalid type {type(df)} for df")

        if schema is None:
            schema = HistorySchema.from_dict({})
        elif not isinstance(schema, HistorySchema):
            raise ValueError(f"Invalid type {type(schema)} for schema")

        df.index = pd.MultiIndex.from_tuples(
            df.index, names=[level.value for level in schema.levels]
        )

        self.df = df
        self.schema = schema
        self.update_schema()

    def update_schema(self):
        self.schema.security_manager.add_list([security for security in self.level_unique(HistoryLevel.SECURITY)
                                               if security not in self.schema.security_manager])
        self.schema.fields = self.df.columns.tolist()

    def update_df(self):
        self.df.index = pd.MultiIndex.from_tuples(
            self.df.index, names=[level.value for level in self.schema.levels]
        )
        if HistoryLevel.SECURITY in self.schema.levels:
            self.df.index = self.df.index.set_levels(
                [self.schema.security_manager.get(security) for security in self.df.index.levels[1]],
                level=HistoryLevel.SECURITY.value
            )

    def __repr__(self):
        return self.df.__repr__()

    def __dict__(self):
        return {
            "df": self.df.to_dict(),
            "schema": self.schema.__dict__(),
        }

    def __iter__(self):
        return self.df.iterrows()

    def __getitem__(self, item):
        return self.df.loc[item]

    @classmethod
    def from_dict(cls, history: dict, schema: HistorySchema | None = None):
        return cls(
            history.get("df", None), HistorySchema.from_dict(history.get("schema", {}) if schema is None else schema)
        )

    @classmethod
    def from_tuple(cls, history: tuple, schema: HistorySchema | None = None):
        return cls(pd.DataFrame([history[1]], index=pd.MultiIndex.from_tuples([history[0]])), schema)

    def __add__(self, other: History):
        if not isinstance(other, History):
            raise ValueError(f"Invalid type {type(other)} for other")

        securities = set(
            self.level_unique(HistoryLevel.SECURITY)
            + other.level_unique(HistoryLevel.SECURITY)
        )
        security_manager = SecurityManager.from_list(list(securities))

        # Can't infer schema between two histories
        return History(pd.concat([self.df, other.df]), schema=HistorySchema(security_manager=security_manager))

    def __iadd__(self, other: History):
        if not isinstance(other, History):
            raise ValueError(f"Invalid type {type(other)} for other")

        self.df = pd.concat([self.df, other.df])

        # Infer schema to left history
        self.update_schema()
        return self

    @property
    def shape(self):
        return self.df.shape

    def level_unique(self, level: HistoryLevel = HistoryLevel.SECURITY):
        return self.df.index.get_level_values(level.value).unique().tolist()

    def levels_unique(self, levels: List[HistoryLevel] = None) -> Dict[HistoryLevel, list]:
        if levels is None:
            levels = self.schema.levels
        return {level: self.level_unique(level) for level in levels if level in self.schema.levels}

    def set_level(self, values, level: HistoryLevel = HistoryLevel.SECURITY):
        if self.df.empty:
            return
        self.df.index = self.df.index.set_levels(values, level=level)

    def get_df(
            self, levels: Dict[HistoryLevel, list] = None, fields: List[str] = None
    ) -> pd.DataFrame:
        if self.df.empty:
            return pd.DataFrame()

        if levels is None:
            levels = self.levels_unique()
        if fields is None:
            fields = self.schema.fields

        masks = reduce(
            lambda x, y: x & y,
            (self.df.index.get_level_values(level.value).isin(values) for level, values in levels.items()),
        )

        df = self.df[masks]

        return df[fields] if not df.empty else pd.DataFrame()

    def set_df(
            self,
            levels: Dict[HistoryLevel, list] = None,
            fields: List[str] = None,
            values: pd.DataFrame | dict = None,
    ):
        if self.df.empty:
            return

        if levels is None:
            levels = self.levels_unique()
        if fields is None:
            fields = self.schema.fields

        if values is None:
            values = pd.DataFrame()

        df = self.df.copy()

        for level, value in levels.items():
            df.index = df.index.set_levels(value, level=level)

        df[fields] = values[fields]

        self.df = df

    def get(
            self, levels: Dict[HistoryLevel, list] = None, fields: List[str] = None
    ) -> History:
        """
        Get historical data for a given security, field and date

        Args:

        Returns:
            pandas DataFrame with multi-index and fields as columns
        """
        return History(self.get_df(levels, fields), self.schema)

    def add(self, data: History | pd.DataFrame | tuple | dict):
        """
        Add historical data to history

        Args:
            data: pandas DataFrame or History object

        Examples:
            >>> bars = {
                    ('2024-01-01', 'AAPL'): Bar(close=155, open=150, high=160, low=140, volume=1000000, vwap=150),
                    ('2024-01-01', 'MSFT'): Bar(close=255, open=250, high=260, low=240, volume=2000000, vwap=250)
                }
            >>> history = History(data)
            >>> history.add({
                    ('2024-01-02', 'AAPL'): Bar(close=160, open=155, high=165, low=145, volume=1000000, vwap=155),
                    ('2024-01-02', 'MSFT'): Bar(close=260, open=255, high=265, low=245, volume=2000000, vwap=255)
                })
            >>> history.get(securities='AAPL', fields='close', dates='2024-01-02')
            # Output:
            # date        security
            # 2024-01-02  AAPL      160
            # Name: close, dtype: int64
        """
        if isinstance(data, History):
            data = data.df
        elif isinstance(data, tuple):
            data = pd.DataFrame([data[1]], index=pd.MultiIndex.from_tuples([data[0]]))
        elif isinstance(data, dict):
            data = pd.DataFrame(data)
        elif not isinstance(data, pd.DataFrame):
            raise ValueError(f"Invalid type {type(data)} for data")
        # Dangerous to concat here because it might not keep index
        self.df = pd.concat([self.df, data])
        # so we call update_df to make sure index is correct
        self.schema.security_manager.add([security for security in self.level_unique(HistoryLevel.SECURITY)
                                          if security not in self.schema.security_manager])
        self.update_df()
        self.update_schema()

    def set(self, fields: List[str] = None, values: pd.DataFrame | dict = None):
        """
        Set historical data for a given security, field and date

        Args:
            fields: list of bar fields
            values: pandas DataFrame or dict with multi-index and bar fields as columns

        Examples:
            >>> history = History()
            >>> history.set(
                    fields=['close'],
                    values={
                        ('2024-01-01', 'AAPL'): 155,
                        ('2024-01-01', 'MSFT'): 255
                    }
                )
            >>> history.get(securities='AAPL', fields='close', dates='2024-01-01')
            # Output:
            # date        security
            # 2024-01-01  AAPL      155
            # Name: close, dtype: int64
        """
        if values is None:
            values = pd.DataFrame()

        if isinstance(values, pd.DataFrame):
            values = values.to_dict()
        elif not isinstance(values, dict):
            raise ValueError(f"Invalid type {type(values)} for values")

        self.set_df(fields=fields, values=values)

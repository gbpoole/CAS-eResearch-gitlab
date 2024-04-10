import sqlite3
import json
from datetime import datetime, timedelta
import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict
from dateutil.relativedelta import relativedelta
from pandas.api.types import is_list_like
from pathlib import Path
from collections.abc import Iterable
from pandas.core.frame import DataFrame


class BaseException(Exception):
    """Base class for exceptions"""

    def __init__(self, message: str):
        self._message = message

    def __str__(self) -> str:
        return f"{self._message}"


class InvalidGroupError(BaseException):
    """Raised when an attempt is made to reference an invalid group"""

    pass


class Groups(object):
    def __init__(self, ds_in: "DataSet", columns: Iterable[str] | str):

        # Validate that the columns passed in is a string or list of strings
        if isinstance(columns, str):
            columns = [columns]
        elif isinstance(columns, Iterable):
            for column in columns:
                if not isinstance(column, str):
                    raise TypeError("'columns' is an iterable, but not of strings")
        else:
            raise TypeError("'columns' is not string or iterable of strings")

        self._ds = ds_in
        self._subgroups = self._ds.df.groupby(by=columns)
        self._group_names = self._subgroups.indices
        self._group_columns = columns

    def get_by_name(self, columns: str) -> DataFrame:
        try:
            if is_list_like(columns):
                if len(columns) <= 1:
                    df = self._subgroups.get_group((columns,))
                else:
                    df = self._subgroups.get_group(columns)
            else:
                df = self._subgroups.get_group((columns,))
        except NameError as e:
            raise InvalidGroupError(f"Invalid group name: {columns}") from e
        return df

    def reorder(self, column=None, ascending=False):
        if column is not None:
            self._group_names = (
                self._subgroups[column].sum().sort_values(ascending=ascending).index
            )
        else:
            self._group_names = self._subgroups.indices
        return self

    def time_series(self, group_name: str, column="time") -> None:
        group = self.get_by_name(group_name)
        return (
            group.groupby(pd.Grouper(freq="ME", closed="left", label="left"))[column]
            .sum()
            .reset_index()
        )

    def list(self):
        for i_group, group_name in enumerate(self._group_names):
            print(f"{i_group:04}[{len(self.get_by_name(group_name)):04}]: {group_name}")

    def __iter__(self):
        for group_name in self._group_names:
            yield self.get_by_name(group_name)

    def plot(self, groups: Iterable[str] = None, plot="time", n=None, title=None):

        if groups:

            # Validate that the groups passed in is a string or list of strings
            if isinstance(groups, str):
                group_names = [groups]
            elif isinstance(groups, Iterable):
                for group_name in groups:
                    if not isinstance(group_name, str):
                        raise TypeError("'groups' is an iterable, but not of strings")
            else:
                raise TypeError("'groups' is not string or iterable of strings")

            group_names = groups

        else:
            group_names = self._group_names

        sns.set_theme()
        fig, ax = plt.subplots()
        ax.set_ylabel("Monthly Total [h]")
        ax.set_xlabel("Date")

        bottom_master = np.zeros(len(self._ds.dates))
        sum_other = np.zeros(len(self._ds.dates))

        for i_group, group_name in enumerate(group_names):
            time_series = self.time_series(group_name, column=plot)
            dates = time_series["date"]
            amounts = time_series[plot]

            if n is None or i_group < n:
                bottom = np.zeros(len(dates))
                for i_date, date in enumerate(dates):
                    bottom[i_date] = bottom_master[self._ds.dates.index(date)]
                ax.bar(
                    dates,
                    amounts,
                    width=relativedelta(months=1),
                    bottom=bottom,
                    label=group_name,
                )
                for date, amount in zip(dates, amounts):
                    bottom_master[self._ds.dates.index(date)] += amount
            else:
                for date, amount in zip(dates, amounts):
                    sum_other[self._ds.dates.index(date)] += amount

        if n is not None:
            ax.bar(
                self._ds.dates,
                sum_other,
                width=relativedelta(months=1),
                bottom=bottom_master,
                label="Other",
            )
        ax.legend()
        if title:
            ax.set_title(title)
        fig.autofmt_xdate()

        if title:
            filename_fig = f"plot_{title}.pdf"
        else:
            if len(group_names) == 1:
                filename_fig = f"plot_{group_names[0]}.pdf"
            else:
                filename_fig = "plot_groups.pdf"
        fig.savefig(filename_fig)
        plt.close()
        print(f"Figure written to file: {filename_fig}")


class DataSet(object):
    def __init__(self, path: str | Path = None, df=None):

        # Either path or df needs to be passed
        if path is None and df is None:
            raise ValueError(
                "Neither a path nor a dataframe were given to the constructor."
            )

        if df is not None:
            if "date" not in df:
                df.reset_index(inplace=True)
            dfs = [df]
        else:
            dfs = []

        if path:
            for filename_in in [
                filename for filename in os.listdir(path) if filename.endswith(".db")
            ]:

                table_name = "events"
                time_str_fmt = "%Y-%m-%d %H:%M:%S.%f"

                def timedelta_to_hours(delta):
                    hours, remainder = divmod(delta.total_seconds(), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    return hours + minutes / 60.0

                # Create a SQL connection to our SQLite database
                con = sqlite3.connect(filename_in)

                # Read event table into a dataframe
                df_sql = pd.read_sql_query(f"SELECT * from {table_name}", con)

                # Select time entry events and create new dataframe
                event_list = []
                for i_payload, (time_str, payload_str) in enumerate(
                    zip(df_sql.time, df_sql.payload)
                ):
                    event_time = datetime.strptime(time_str, time_str_fmt)
                    payload = json.loads(payload_str)
                    user = payload["user"]
                    project = payload["project"]
                    changes = payload["changes"]
                    metadata = payload["object_attributes"]

                    if "total_time_spent" in changes.keys():
                        # print(json.dumps(payload,sort_keys=True,indent=4))
                        t_1 = changes["total_time_spent"]["previous"]
                        t_2 = changes["total_time_spent"]["current"]
                        delta = timedelta(seconds=(t_2 - t_1))
                        event_list.append(
                            [
                                event_time,
                                user["name"],
                                f"{project['namespace']}/{project['name']}",
                                timedelta_to_hours(delta),
                                metadata["title"],
                            ]
                        )

                df = pd.DataFrame(
                    event_list, columns=["date", "dev", "project", "time", "issue"]
                )

                df["month"] = df["date"].apply(lambda row: f"{row:%Y-%m}")

                dfs.append(df)

        self.df = pd.concat(dfs, ignore_index=True)
        self.df = self.df.set_index("date")
        self.df.sort_index(inplace=True)

        # Date range
        self.date_min = self.df.index.min()
        self.date_max = self.df.index.max()
        # print(f"Date range: {self.date_min} -> {self.date_max}")

        self.time_t = self.df.groupby(
            pd.Grouper(freq="ME", closed="left", label="left")
        )["time"].sum()
        self.dates = sorted(self.time_t.index)

    def subselect(self, queries: Dict):
        def reformat_string(string_to_escape, reverse=False):
            if reverse:
                return string_to_escape.replace('\\"', '"').replace("\\'", "'")
            else:
                return string_to_escape.replace('"', '\\"').replace("'", "\\'")

        query_string = None
        for query in queries.keys():
            if not query_string:
                query_string = ""
            else:
                query_string = query_string + " & "
            query_string = (
                query_string + f'`{query}` == "{reformat_string(queries[query])}"'
            )

        return DataSet(df=self.df.query(query_string))

    def group(self, columns):
        return Groups(self, columns)

    def count(self):
        return len(self.df)

    def print_list(self, columns=["project", "dev", "time"], sort=None, tail=None):
        if self.count() > 0:
            if sort:
                str_out = self.df.sort_values(by=sort).to_string(columns=columns)
            else:
                str_out = self.df.to_string(columns=columns)
            if tail and tail > 0:
                str_out = "\n".join(str_out.splitlines()[-tail:])
                print(f"Printing last {tail} entries:")
            print(str_out)
            sum_time = self.df["time"].sum()
            print()
            print(f"total time = {sum_time:.1f}h")
        else:
            print("Empty dataset.")

    def print_totals(
        self,
        levels=["dev", "project", "issue"],
        sort_levels=["project", "dev"],
        _i_level=0,
    ):
        level = levels[0]
        groups = self.group(level).reorder(column="time", ascending=False)

        def time_to_string(time: int) -> str:
            weeks = time / 40.0
            if weeks < 1:
                return f"{time}h"
            else:
                return f"{time/40.:.1f}w"

        # Sort order of printing?
        group_names = groups._group_names.values
        if level in sort_levels:
            group_names = sorted(group_names, key=str.casefold)

        # Print lines
        for group in group_names:
            ds_group = self.subselect({f"{level}": group})

            time = 0
            for _, row in ds_group.df.iterrows():
                time = time + row["time"]

            print(f"{4*_i_level*' '}{group}: {time_to_string(time)}")
            if len(levels) > 1:
                self.subselect({f"{level}": group}).print_totals(
                    levels[1:], sort_levels, _i_level + 1
                )

        if _i_level == 1:
            print()

    def print_summary(self, tail=20):
        # Print all records
        self.print_list(tail=tail)

        print("=== Devs ===\n")
        self.print_totals(["dev", "project", "issue"])

        print("=== Projects ===\n")
        self.print_totals(["project", "dev", "issue"])

    def to_json(self):
        return self.df.to_json()

    def plot(self, column="time", n=5):
        prjs = self.group("project").reorder(column=column, ascending=False)
        n_plot_prj = min(n, len(prjs._group_names))
        prjs.plot(n=n_plot_prj, title="Projects")
        for i_prj, prj_name in enumerate(prjs._group_names[0:n_plot_prj]):
            ds_prj = self.subselect({"project": prj_name})
            devs = ds_prj.group("dev").reorder(column=column, ascending=False)
            n_plot_dev = min(n, len(devs._group_names))
            devs.plot(n=n_plot_dev, title=f"{prj_name}")
        devs = self.group("dev").reorder(column=column, ascending=False)
        for i_dev, dev_name in enumerate(devs._group_names[0:n_plot_dev]):
            ds_dev = self.subselect({"dev": dev_name})
            prj = ds_dev.group("project").reorder(column=column, ascending=False)
            n_plot_dev = min(n, len(prj._group_names))
            prj.plot(n=n_plot_dev, title=f"{dev_name}")

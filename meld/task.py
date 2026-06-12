# Copyright (C) 2002-2006 Stephen Kennedy <stevek@gnome.org>
# Copyright (C) 2012-2013 Kai Willadsen <kai.willadsen@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Classes to implement scheduling for cooperative threads."""

import traceback


class SchedulerBase:
    """Base class with common functionality for schedulers

    Derived classes must implement get_current_task.
    """

    def __init__(self):
        self.tasks = []
        self.callbacks = []
        self.suspended_tasks = {}
        self.task_inputs = {}

    def __repr__(self):
        return "%s" % self.tasks

    def connect(self, signal, action):
        assert signal == "runnable"
        if action not in self.callbacks:
            self.callbacks.append(action)

    def add_task(self, task, atfront=False):
        """Add a task to the scheduler's task list

        The task may be a function, generator or scheduler, and is
        deemed to have finished when it returns a false value or raises
        StopIteration.
        """
        self.remove_task(task)

        if atfront:
            self.tasks.insert(0, task)
        else:
            self.tasks.append(task)

        for callback in self.callbacks:
            callback(self)

    def remove_task(self, task):
        """Remove a single task from the scheduler"""
        try:
            self.tasks.remove(task)
        except ValueError:
            pass
        for fut, t in list(self.suspended_tasks.items()):
            if t == task:
                del self.suspended_tasks[fut]
        if task in self.task_inputs:
            del self.task_inputs[task]

    def remove_all_tasks(self):
        """Remove all tasks from the scheduler"""
        self.tasks = []
        self.suspended_tasks = {}
        self.task_inputs = {}

    def add_scheduler(self, sched):
        """Adds a subscheduler as a child task of this scheduler"""
        sched.connect("runnable", lambda t: self.add_task(t))

    def remove_scheduler(self, sched):
        """Remove a sub-scheduler from this scheduler"""
        self.remove_task(sched)
        try:
            self.callbacks.remove(sched)
        except ValueError:
            pass

    def get_current_task(self):
        """Overridden function returning the next task to run"""
        raise NotImplementedError

    def _future_done(self, future, task):
        from gi.repository import GLib
        GLib.idle_add(self._resume_task, future, task)

    def _resume_task(self, future, task):
        if future in self.suspended_tasks:
            del self.suspended_tasks[future]
            try:
                res = future.result()
            except Exception as e:
                res = e
            self.task_inputs[task] = res
            self.tasks.append(task)
            for callback in self.callbacks:
                callback(self)

    def __call__(self):
        """Run an iteration of the current task"""
        if len(self.tasks):
            r = self.iteration()
            if r:
                return r
        return self.tasks_pending()

    def complete_tasks(self):
        """Run all of the scheduler's current tasks to completion"""
        from gi.repository import GLib
        while self.tasks_pending():
            if len(self.tasks) == 0 and len(self.suspended_tasks) > 0:
                GLib.MainContext.default().iteration(True)
            else:
                self.iteration()

    def tasks_pending(self):
        return len(self.tasks) != 0 or len(self.suspended_tasks) != 0

    def iteration(self):
        """Perform one iteration of the current task"""
        try:
            task = self.get_current_task()
        except StopIteration:
            return 0
        try:
            if hasattr(task, "__iter__"):
                if task in self.task_inputs:
                    val = self.task_inputs.pop(task)
                    if isinstance(val, Exception):
                        ret = task.throw(val)
                    else:
                        ret = task.send(val)
                else:
                    ret = next(task)
            else:
                ret = task()
        except StopIteration:
            pass
        except Exception:
            traceback.print_exc()
        else:
            from concurrent.futures import Future
            if isinstance(ret, Future):
                self.suspended_tasks[ret] = task
                if task in self.tasks:
                    self.tasks.remove(task)
                ret.add_done_callback(lambda f: self._future_done(f, task))
                return 1
            if ret:
                return ret
        if task in self.tasks:
            self.tasks.remove(task)
        return 0



class LifoScheduler(SchedulerBase):
    """Scheduler calling most recently added tasks first"""

    def get_current_task(self):
        try:
            return self.tasks[-1]
        except IndexError:
            raise StopIteration


class FifoScheduler(SchedulerBase):
    """Scheduler calling tasks in the order they were added"""

    def get_current_task(self):
        try:
            return self.tasks[0]
        except IndexError:
            raise StopIteration


if __name__ == "__main__":
    import random
    import time
    m = LifoScheduler()

    def timetask(t):
        while time.time() - t < 1:
            print("***")
            time.sleep(0.1)
        print("!!!")

    def sayhello(x):
        for i in range(random.randint(2, 8)):
            print("hello", x)
            time.sleep(0.1)
            yield 1
        print("end", x)

    s = FifoScheduler()
    m.add_task(s)
    s.add_task(sayhello(10))
    s.add_task(sayhello(20))
    s.add_task(sayhello(30))
    while s.tasks_pending():
        s.iteration()
    time.sleep(2)
    print("***")

import builtins
import warnings
from gc import get_referents

from system.classes.builtins import (ObjectTransformer, asDict,
                                     boolean_to_emoji, calculate_, catch,
                                     chunk, get_error, human_join,
                                     human_timedelta, humanize, humanize_,
                                     hyperlink, maximum, maximum_, minimum,
                                     minimum_, number, positive, positive_)
from system.classes.builtins import shorten as shorten_
from system.classes.builtins import shorten__, suppress_error
from system.honest import Honest

warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.simplefilter("ignore", ResourceWarning)

"""
Overriding builtins in python's memory
"""
builtins.human_join = human_join
builtins.human_timedelta = human_timedelta
builtins.boolean_to_emoji = boolean_to_emoji
builtins.calculate = calculate_
builtins.catch = catch
builtins.get_error = get_error
builtins.suppress_error = suppress_error
builtins.hyperlink = hyperlink
builtins.ObjectTransformer = ObjectTransformer
builtins.asDict = asDict
_float = get_referents(float.__dict__)[0]
_str = get_referents(str.__dict__)[0]
_int = get_referents(int.__dict__)[0]
_list = get_referents(list.__dict__)[0]
__list = get_referents(builtins.list.__dict__)[0]
__float = get_referents(builtins.float.__dict__)[0]
__int = get_referents(builtins.int.__dict__)[0]
__str = get_referents(builtins.str.__dict__)[0]
_float["maximum"] = maximum
_float["minimum"] = minimum
_float["positive"] = positive
__float["maximum"] = maximum
__float["minimum"] = minimum
__float["positive"] = positive
_int["maximum"] = maximum_
_int["humanize"] = humanize
_list["chunk"] = chunk
__list["chunk"] = chunk
_list["number"] = number
__list["number"] = number
_int["minimum"] = minimum_
_int["positive"] = positive_
__int["maximum"] = maximum_
__int["minimum"] = minimum_
__int["humanize"] = humanize
__int["positive"] = positive_
_str["shorten"] = shorten__
_str["humanize"] = humanize_
__str["humanize"] = humanize_
__str["shorten"] = shorten__
builtins.shorten = shorten_


"""
Bot Initialization
"""

bot = Honest()

if __name__ == "__main__":
    bot.run()

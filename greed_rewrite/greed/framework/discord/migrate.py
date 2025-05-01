from discord import (
    Guild,
    AutoModTrigger,
    AutoModRuleTriggerType,
    AutoModRuleAction,
    utils,
    TextChannel,
    AutoModRuleEventType,
    ForumChannel,
    Role,
)
from discord.ext.commands import CommandError
from typing import Union, Optional, List

invite_regex = r"(?:https?://)?discord(?:app)?\.(?:com/invite|gg)/[a-zA-Z0-9]+/?"


def str_to_action(string: str):
    action_map = {
        "timeout": AutoModRuleAction.timeout,
        "mute": AutoModRuleAction.timeout,
        "block": AutoModRuleAction.block_message,
    }
    return action_map.get(string.lower(), AutoModRuleAction.send_alert_message)


async def add_keyword(
    guild: Guild, keyword: Union[str, List[str]], migrate: Optional[bool] = False
) -> bool:
    automod_rules = await guild.fetch_automod_rules()
    keyword_rule = utils.get(automod_rules, name=f"keywords")

    if keyword_rule:
        if migrate:
            raise CommandError("Your **keywords** have already been migrated")
        if keyword_rule.trigger.type == AutoModRuleTriggerType.keyword:
            keywords_to_add = keyword if isinstance(keyword, list) else [keyword]
            # Limit each keyword to 59 characters
            keywords_to_add = [k[:59] for k in keywords_to_add]
            
            new_keywords = keyword_rule.trigger.keyword_filter + keywords_to_add
            if len(new_keywords) > 1000:
                raise CommandError("You are limited to 1000 filtered words")
            trigger = AutoModTrigger(
                type=AutoModRuleTriggerType.keyword, keyword_filter=new_keywords
            )
            await keyword_rule.edit(trigger=trigger)
            return True
    else:
        if migrate:
            keywords = [keyword] if isinstance(keyword, str) else keyword
            await guild.create_automod_rule(
                name="keywords",
                event_type=AutoModRuleEventType.message_send,
                trigger=AutoModTrigger(keyword_filter=keywords),
                enabled=True,
                actions=[
                    AutoModRuleAction(
                        custom_message="The bot Blocked you from saying this"
                    )
                ],
            )
            return True
    return False


async def clear_keywords(guild: Guild) -> bool:
    automod_rules = await guild.fetch_automod_rules()
    keyword_rule = utils.get(automod_rules, name="keywords")
    if keyword_rule:
        await keyword_rule.delete()
        return True
    return False


async def remove_keyword(guild: Guild, keyword: str) -> bool:
    automod_rules = await guild.fetch_automod_rules()
    keyword_rule = utils.get(automod_rules, name="keywords")
    if keyword_rule and keyword_rule.trigger.type == AutoModRuleTriggerType.keyword:
        new_keywords = keyword_rule.trigger.keyword_filter
        new_keywords.remove(keyword[:59])
        trigger = AutoModTrigger(
            type=AutoModRuleTriggerType.keyword, keyword_filter=new_keywords
        )
        await keyword_rule.edit(trigger=trigger)
        return True
    return False


async def exempt(guild: Guild, obj: Union[TextChannel, ForumChannel, Role]) -> bool:
    rules = await guild.fetch_automod_rules()
    for rule in rules:
        kwargs = {}
        if isinstance(obj, (TextChannel, ForumChannel)):
            kwargs["exempt_channels"] = rule.exempt_channels + [obj]
        else:
            kwargs["exempt_roles"] = rule.exempt_roles + [obj]
        await rule.edit(**kwargs)
    return True

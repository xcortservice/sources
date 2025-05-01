from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

THRESHOLD = 0.70
SEXUAL_THRESHOLD = 0.30


class Request(BaseModel):
    id: Optional[str] = None
    timestamp: Optional[float] = None
    operations: Optional[int] = None


class CleavageCategories(BaseModel):
    very_revealing: Optional[float] = None
    revealing: Optional[float] = None
    none: Optional[float] = None


class MaleChestCategories(BaseModel):
    very_revealing: Optional[float] = None
    revealing: Optional[float] = None
    slightly_revealing: Optional[float] = None
    none: Optional[float] = None


class SuggestiveClasses(BaseModel):
    bikini: Optional[float] = None
    cleavage: Optional[float] = None
    cleavage_categories: Optional[CleavageCategories] = None
    lingerie: Optional[float] = None
    male_chest: Optional[float] = None
    male_chest_categories: Optional[MaleChestCategories] = None
    male_underwear: Optional[float] = None
    miniskirt: Optional[float] = None
    minishort: Optional[float] = None
    nudity_art: Optional[float] = None
    schematic: Optional[float] = None
    sextoy: Optional[float] = None
    suggestive_focus: Optional[float] = None
    suggestive_pose: Optional[float] = None
    swimwear_male: Optional[float] = None
    swimwear_one_piece: Optional[float] = None
    visibly_undressed: Optional[float] = None
    other: Optional[float] = None


class Context(BaseModel):
    sea_lake_pool: Optional[float] = None
    outdoor_other: Optional[float] = None
    indoor_other: Optional[float] = None


class Nudity(BaseModel):
    sexual_activity: Optional[float] = None
    sexual_display: Optional[float] = None
    erotica: Optional[float] = None
    very_suggestive: Optional[float] = None
    suggestive: Optional[float] = None
    mildly_suggestive: Optional[float] = None
    suggestive_classes: Optional[SuggestiveClasses] = None
    none: Optional[float] = None
    context: Optional[Context] = None


class Classes(BaseModel):
    firearm: Optional[float] = None
    firearm_gesture: Optional[float] = None
    firearm_toy: Optional[float] = None
    knife: Optional[float] = None


class FirearmType(BaseModel):
    animated: Optional[float] = None


class FirearmAction(BaseModel):
    aiming_threat: Optional[float] = None
    aiming_camera: Optional[float] = None
    aiming_safe: Optional[float] = None
    in_hand_not_aiming: Optional[float] = None
    worn_not_in_hand: Optional[float] = None
    not_worn: Optional[float] = None


class Weapon(BaseModel):
    classes: Optional[Classes] = None
    firearm_type: Optional[FirearmType] = None
    firearm_action: Optional[FirearmAction] = None


class Classes1(BaseModel):
    cannabis: Optional[float] = None
    cannabis_logo_only: Optional[float] = None
    cannabis_plant: Optional[float] = None
    cannabis_drug: Optional[float] = None
    recreational_drugs_not_cannabis: Optional[float] = None


class RecreationalDrug(BaseModel):
    prob: Optional[float] = None
    classes: Optional[Classes1] = None


class Classes2(BaseModel):
    pills: Optional[float] = None
    paraphernalia: Optional[float] = None


class Medical(BaseModel):
    prob: Optional[float] = None
    classes: Optional[Classes2] = None


class Offensive(BaseModel):
    prob: Optional[float] = None
    nazi: Optional[float] = None
    confederate: Optional[float] = None
    supremacist: Optional[float] = None
    terrorist: Optional[float] = None
    middle_finger: Optional[float] = None


class Text(BaseModel):
    profanity: Optional[List] = None
    personal: Optional[List] = None
    link: Optional[List] = None
    social: Optional[List] = None
    extremism: Optional[List] = None
    medical: Optional[List] = None
    drug: Optional[List] = None
    weapon: Optional[List] = None
    content_trade: Optional[List] = Field(None, alias="content-trade")
    money_transaction: Optional[List] = Field(None, alias="money-transaction")
    spam: Optional[List] = None
    violence: Optional[List] = None
    self_harm: Optional[List] = Field(None, alias="self-harm")


class Classes3(BaseModel):
    very_bloody: Optional[float] = None
    slightly_bloody: Optional[float] = None
    body_organ: Optional[float] = None
    serious_injury: Optional[float] = None
    superficial_injury: Optional[float] = None
    corpse: Optional[float] = None
    skull: Optional[float] = None
    unconscious: Optional[float] = None
    body_waste: Optional[float] = None
    other: Optional[float] = None


class Type(BaseModel):
    animated: Optional[float] = None
    fake: Optional[float] = None
    real: Optional[float] = None


class Gore(BaseModel):
    prob: Optional[float] = None
    classes: Optional[Classes3] = None
    type: Optional[Type] = None


class Classes4(BaseModel):
    physical_violence: Optional[float] = None
    firearm_threat: Optional[float] = None
    combat_sport: Optional[float] = None


class Violence(BaseModel):
    prob: Optional[float] = None
    classes: Optional[Classes4] = None


class Type1(BaseModel):
    real: Optional[float] = None
    fake: Optional[float] = None
    animated: Optional[float] = None


class SelfHarm(BaseModel):
    prob: Optional[float] = None
    type: Optional[Type1] = None


class Media(BaseModel):
    id: Optional[str] = None
    uri: Optional[str] = None


class ImageModeration(BaseModel):
    status: Optional[str] = None
    request: Optional[Request] = None
    nudity: Optional[Nudity] = None
    weapon: Optional[Weapon] = None
    recreational_drug: Optional[RecreationalDrug] = None
    medical: Optional[Medical] = None
    offensive: Optional[Offensive] = None
    text: Optional[Text] = None
    faces: Optional[List] = None
    gore: Optional[Gore] = None
    violence: Optional[Violence] = None
    self_harm: Optional[SelfHarm] = Field(None, alias="self-harm")
    media: Optional[Media] = None

    @property
    def nsfw(self) -> bool:
        return any(
            [
                self.nudity.none < 0.80,
                self.nudity.erotica > THRESHOLD,
                self.nudity.sexual_activity > SEXUAL_THRESHOLD,
                self.nudity.sexual_display > SEXUAL_THRESHOLD,
                self.gore.prob > THRESHOLD,
                self.medical.prob > THRESHOLD,
                self.recreational_drug.prob > THRESHOLD,
                self.weapon.classes.firearm > THRESHOLD,
                self.weapon.classes.knife > THRESHOLD,
                self.offensive.prob > THRESHOLD,
                self.self_harm.prob > THRESHOLD,
            ]
        )

# Deskrawl — ScriptableObject / 数值类 字段模式（由 dump.cs 提取）

## 枚举

### StyleSyntaxTokenType  (TypeDefIndex 5482, underlying: int)
- Unknown = 0
- String = 1
- Number = 2
- Space = 3
- SingleBar = 4
- DoubleBar = 5
- DoubleAmpersand = 6
- Comma = 7
- SingleQuote = 8
- Asterisk = 9
- Plus = 10
- QuestionMark = 11
- HashMark = 12
- ExclamationPoint = 13
- OpenBracket = 14
- CloseBracket = 15
- OpenBrace = 16
- CloseBrace = 17
- LessThan = 18
- GreaterThan = 19
- End = 20

### ProjectileTravelMode  (TypeDefIndex 5560, underlying: int)
- Physics = 0
- LaneLocked = 1
- Orbit = 2
- Wandering = 3
- Parabola = 4

### ParabolaTimingMode  (TypeDefIndex 5561, underlying: int)
- FixedDuration = 0
- FixedSpeed = 1

### WanderCenterMode  (TypeDefIndex 5562, underlying: int)
- SpawnPoint = 0
- TargetPoint = 1
- Caster = 2

### PrimaryStat  (TypeDefIndex 5571, underlying: int)
- Strength = 0
- Dexterity = 1
- Intelligence = 2

### EncounterType  (TypeDefIndex 5572, underlying: int)
- Normal = 0
- Elite = 1
- Boss = 2

### PlayerCondition  (TypeDefIndex 5573, underlying: int)
- Injured = 0
- Healthy = 1
- NoNearbyEnemies = 2
- OutOfCombat = 3
- SingleEnemyInCombat = 4
- Surrounded = 5
- None = -1

### AbilityTag  (TypeDefIndex 5574, underlying: int)
- None = 9999
- BasicAttack = 0
- StrongAttack = 1
- Special = 2
- AOE = 3
- Warcry = 4
- Bleed = 5
- Enchanted = 6
- Physical = 7
- Fire = 8
- Frost = 9
- Lightning = 10
- Poison = 11
- Chi = 12
- Aracane = 13
- Trap = 14
- Summon = 15
- BlindingShot = 16

### TargetingShape  (TypeDefIndex 5576, underlying: int)
- Target = 0
- Self = 1
- PointAoE = 2
- Cone = 3
- AllInRadius = 4
- Random = 5
- None = 6
- Player = 7
- DeadAllies = 8
- Line = 9
- RandomAllies = 10

### TargetAffinity  (TypeDefIndex 5577, underlying: int)
- Enemies = 0
- Player = 1

### TriggerType  (TypeDefIndex 5578, underlying: int)
- Cooldown = 0
- OnDeath = 1

### DamageType  (TypeDefIndex 5579, underlying: int)
- Physical = 0
- Fire = 1
- Cold = 2
- Lightning = 3
- Poison = 4
- Arcane = 5

### StatType  (TypeDefIndex 5580, underlying: int)
- Strength = 0
- Dexterity = 1
- Intelligence = 2
- Damage = 3
- CritChance = 4
- CritDamage = 5
- AttackSpeed = 6
- MaxHealth = 7
- MaxHealthPercent = 42
- Armor = 8
- ArmorPercent = 44
- MagicResist = 9
- MagicResistPercent = 59
- Dodge = 22
- CritDamageReduction = 60
- DamageReduction = 64
- PoisonDamageReduction = 49
- PhysicalDamageReduction = 51
- FireDamageReduction = 52
- ColdDamageReduction = 53
- LightningDamageReduction = 54
- ArcaneDamageReduction = 55
- MoveSpeed = 10
- MoveSpeedPercent = 57
- LifeOnHit = 11
- LifeOnKill = 12
- CooldownReduction = 13
- MaxMana = 14
- GoldFind = 15
- MagicFind = 16
- HpPotionFind = 17
- Capacity = 18
- MaterialFind = 19
- WeaponDamage = 20
- WeaponSpeed = 21
- DamagePhysical = 23
- DamageFire = 24
- DamageCold = 25
- DamageLightning = 26
- DamagePoison = 27
- DamageArcane = 28
- DamagePercent = 65
- DamageVsHealthy = 29
- DamageVsInjured = 30
- DamageVsSlowed = 31
- DamageVsElite = 32
- VulnerableDamage = 40
- DamageVsImmobilized = 43
- DamageVsBleeding = 45
- DamageVsPoisoned = 46
- DamageVsDistant = 58
- BasicAttackDamage = 33
- StrongAttackDamage = 34
- SpecialAbilityDamage = 61
- DamageOverTime = 62
- DamageVsBurned = 63
- ManaOnKill = 35
- LifeRegen = 36
- HealingReceivedBonus = 56
- ManaRegen = 47
- ManaCostReduction = 37
- PotionCharges = 38
- Thorns = 39
- XPGain = 41
- ThornsDamagePercent = 48
- GemSlots = 50

### GemCategory  (TypeDefIndex 5581, underlying: int)
- Armor = 0
- Accessory = 1
- Weapon = 2

### AttributeCategory  (TypeDefIndex 5584, underlying: int)
- Primary = 0
- Secondary = 1
- Legendary = 2

### StatRole  (TypeDefIndex 5586, underlying: int)
- Offense = 0
- Defense = 1
- Utility = 2

### ModifierType  (TypeDefIndex 5589, underlying: int)
- Flat = 0
- PercentAdd = 1
- PercentMult = 2

### VFXAnchor  (TypeDefIndex 5593, underlying: int)
- Transform = 0
- BodyMarker = 1
- TopMarker = 2

### DotReapplyMode  (TypeDefIndex 5600, underlying: int)
- HighestDamageOverwrite = 0
- Pooling = 1
- Stackable = 2

### DeflectTargeting  (TypeDefIndex 5766, underlying: int)
- Nearest = 0
- Random = 1

### TargetStateCondition  (TypeDefIndex 5780, underlying: int)
- Vulnerable = 0
- Stunned = 1
- Slowed = 2
- Elite = 3
- Immobilized = 4
- SpecificStatus = 5
- Distant = 6

### StatusGainCondition  (TypeDefIndex 5785, underlying: int)
- Always = 0
- Moving = 1
- Standing = 2

### ConsumedResource  (TypeDefIndex 5797, underlying: int)
- Mana = 0
- Health = 1

### DotDetonateTiming  (TypeDefIndex 5802, underlying: int)
- OnCast = 0
- OnHit = 1

### StatusTriggerMode  (TypeDefIndex 5809, underlying: int)
- Expired = 0
- WhileActive = 1

### ParagonCategory  (TypeDefIndex 5819, underlying: int)
- Core = 0
- Offense = 1
- Defense = 2
- Utility = 3

### FontRole  (TypeDefIndex 5827, underlying: int)
- Title = 0
- Subtitle = 1
- Paragraph = 2

### HeroClass  (TypeDefIndex 5831, underlying: int)
- None = 0
- Barbarian = 1
- Mage = 2
- Hunter = 4
- Monk = 8
- All = 15

### ItemType  (TypeDefIndex 5834, underlying: int)
- Material = 1
- Consumable = 2
- Equipment = 3
- RandomEquipment = 4
- Rune = 5
- Gem = 6
- Commodity = 7

### ItemRarity  (TypeDefIndex 5835, underlying: int)
- Common = 0
- Uncommon = 1
- Rare = 2
- Legendary = 3
- Divine = 4
- RuneSet = 5

### ItemEffect  (TypeDefIndex 5836, underlying: int)
- None = 0
- UnlockSlave = 1
- OpenChest = 2
- TempBuff = 3

### BuffCategory  (TypeDefIndex 5837, underlying: int)
- None = 0
- CombatPotion = 1
- UtilityPotion = 2
- Food = 3

### EquipSlotType  (TypeDefIndex 5838, underlying: int)
- None = 0
- Weapon = 1
- Helm = 2
- Chest = 3
- Pants = 4
- Boots = 5
- Belt = 6
- Ring = 7
- Necklace = 8
- Gloves = 9
- Shoulder = 10
- Back = 11

### LifeSkillFeature  (TypeDefIndex 5852, underlying: int)
- AutoTownRecovery = 0
- AutoTownPotionRefill = 1
- CarriageAutoFillInventory = 3
- CarriageAutoSell = 4
- OfflineRewards = 5
- CarriageAutoSalvage = 6

### CombatMapType  (TypeDefIndex 5868, underlying: int)
- Normal = 0
- Mythic = 1
- Training = 2
- Treasure = 3

### QuestRequirementType  (TypeDefIndex 5871, underlying: int)
- PlayerLevel = 0
- MapCompleted = 1
- FinalBossCleared = 2

### SlaveSpecies  (TypeDefIndex 5883, underlying: int)
- Humanoid = 0
- Beast = 1
- Undead = 2
- Demon = 3
- Dragon = 4
- Elemental = 5

### MythicEnemySize  (TypeDefIndex 5941, underlying: int)
- Small = 1
- Medium = 2
- Large = 3

### PickupSource  (TypeDefIndex 5951, underlying: int)
- World = 0
- Carriage = 1
- Chest = 2

### GatherMode  (TypeDefIndex 5954, underlying: int)
- Instant = 0
- Cast = 1

### GatherableType  (TypeDefIndex 5955, underlying: int)
- Plant = 0
- Mine = 1

### AudioClipEnum  (TypeDefIndex 5976, underlying: int)
- ButtonHover = 0
- ButtonClick = 1
- MenuOpen = 2
- MenuClose = 3
- ActionFail = 4
- GoldChange = 5
- ReceivedItem = 6
- PotionCharge = 7
- PotionUsed = 8
- GatherMaterial = 9
- EquipChange = 10
- UpgradeStart = 11
- UpgradeSuccess = 12
- UpgradeFailure = 13
- Craft = 14
- OpenChest = 15
- HighRarityDrop = 16
- LevelUp = 17
- AbilityLearned = 18
- AbilityLevelUp = 19
- TalentSpend = 20
- TalentMilestone = 21
- Travel = 22
- ItemHover = 23
- UnlockTownFacility = 24
- AbilityEquip = 25
- Heal = 26
- Teleporting = 27
- TeleportCompletion = 28
- Appearing = 29
- LegendaryDropSpin = 30
- GoldLand = 31
- LockItem = 32
- RuneEquipped = 33
- RuneUnequipped = 34
- GemSocketed = 35
- Salvage = 36
- RevealEnter = 37
- RevealChoiceSelect = 38
- Immune = 39
- NotificationDismissed = 40
- MythicEnter = 41
- MythicTierSelect = 42

### WorldDifficulty  (TypeDefIndex 5993, underlying: int)
- Normal = 0
- Nightmare = 1
- Inferno1 = 2

### WorldDifficultyMask  (TypeDefIndex 5994, underlying: int)
- None = 0
- Normal = 1
- Nightmare = 2
- Inferno1 = 4
- All = -1

### EquipSlotId  (TypeDefIndex 6000, underlying: int)
- Weapon = 0
- Helm = 1
- Chest = 2
- Pants = 3
- Boots = 4
- Belt = 5
- Ring1 = 6
- Ring2 = 7
- Necklace = 8
- Shoulder = 9
- Gloves = 10
- Back = 11

### GameArea  (TypeDefIndex 6007, underlying: int)
- Combat = 0
- Town = 1
- Fishing = 2

### GameState  (TypeDefIndex 6010, underlying: int)
- MainMenu = 0
- Playing = 1

### NotificationCategory  (TypeDefIndex 6079, underlying: int)
- None = 0
- ItemAcquired = 1
- ItemDisposed = 2
- Progression = 3
- ServerError = 4
- ItemLost = 5
- Death = 6

### CharacterMode  (TypeDefIndex 6098, underlying: int)
- Local = 0
- Online = 1


## 类字段（仅序列化字段，按声明顺序）

### AbilityData : ScriptableObject   (TypeDefIndex 5533)
- `AbilityName` : `string`
- `Icon` : `Sprite`
- `Tags` : `List<AbilityTag>`
- `LevelRequirement` : `int`
- `IsLockedInDemo` : `bool`
- `Targeting` : `TargetingShape`
- `Affinity` : `TargetAffinity`
- `Range` : `LeveledFloat`
- `AoERadius` : `float`
- `ConeAngle` : `float`
- `LineWidth` : `float`
- `TargetCount` : `int`
- `ManaGain` : `float`
- `ManaCost` : `LeveledFloat`
- `Cooldown` : `LeveledFloat`
- `CastOutOfCombat` : `bool`
- `ChannelDuration` : `float`
- `ChannelTickRate` : `float`
- `ChannelManaCost` : `LeveledFloat`
- `ChannelMoveForward` : `bool`
- `ChannelLoopAnimBool` : `string`
- `ChannelAllowedCastTags` : `List<AbilityTag>`
- `IsStandingUponCasting` : `bool`
- `StandingTime` : `float`
- `Trigger` : `TriggerType`
- `ChannelWindup` : `float`
- `ChannelRecovery` : `float`
- `SelfStatusOnCast` : `StatusEffectData`
- `AnimationTrigger` : `string`
- `AnimationVariants` : `List<string>`
- `StowWeaponOnBack` : `bool`
- `Effects` : `List<AbilityEffect>`  `[SerializeReference]`
- `CastVFXPrefab` : `GameObject`
- `CastVFXFacesForward` : `bool`
- `CastVFXDelay` : `float`
- `CastSFX` : `AudioClip`
- `CastSFXVolume` : `Vector2`
- `CastSFXPitch` : `Vector2`
- `CastSFXDelay` : `float`
- `ChannelLoopSFX` : `bool`
- `ChannelSFXFadeOut` : `float`
- `UseWeaponTrail` : `bool`
- `WeaponTrailLength` : `float`
- `WeaponTrailStartDelay` : `float`
- `WeaponTrailOffset` : `float`
- `WeaponTrailWidth` : `float`
- `WeaponTrailPrefab` : `GameObject`

### ApplyStatusEffectEffect : AbilityEffect   (TypeDefIndex 5541)
- `StatusEffect` : `StatusEffectData`
- `Chance` : `LeveledFloat`
- `OverrideAffinity` : `bool`
- `AffinityOverride` : `TargetAffinity`
- `ChanceToken` : `TokenSpec`

### DamageEffect : AbilityEffect   (TypeDefIndex 5542)
- `BaseDamage` : `long`
- `AttackScaling` : `LeveledFloat`
- `CanCrit` : `bool`
- `IsDirect` : `bool`
- `DamageType` : `DamageType`
- `MoveStutter` : `float`
- `AttackScalingToken` : `TokenSpec`
- `BaseDamageToken` : `TokenSpec`

### DashEffect : AbilityEffect   (TypeDefIndex 5546)
- `value__` : `int`

### EveryNthCastEffect : AbilityEffect   (TypeDefIndex 5547)
- `CastInterval` : `int`
- `Target` : `TargetAffinity`
- `TriggeredEffects` : `List<AbilityEffect>`  `[SerializeReference]`
- `ReplacesOtherEffects` : `bool`

### GainManaEffect : AbilityEffect   (TypeDefIndex 5548)
- `BaseMana` : `LeveledFloat`
- `PercentMaxMana` : `LeveledFloat`
- `ScalingStat` : `StatType`
- `StatScaling` : `float`
- `ShowManaPopup` : `bool`
- `BaseManaToken` : `TokenSpec`
- `PercentMaxManaToken` : `TokenSpec`
- `StatScalingToken` : `TokenSpec`

### HealEffect : AbilityEffect   (TypeDefIndex 5549)
- `BaseHeal` : `long`
- `AttackScaling` : `float`
- `ManaSpentScaling` : `float`
- `PercentHeal` : `LeveledFloat`
- `OverrideAffinity` : `bool`
- `AffinityOverride` : `TargetAffinity`
- `BaseHealToken` : `TokenSpec`
- `AttackScalingToken` : `TokenSpec`
- `ManaSpentScalingToken` : `TokenSpec`
- `PercentHealToken` : `TokenSpec`

### KnockbackEffect : AbilityEffect   (TypeDefIndex 5551)
- `value__` : `int`

### PullEffect : AbilityEffect   (TypeDefIndex 5553)
- `Speed` : `float`
- `ExtraStandoff` : `float`

### ReviveAllEffect : AbilityEffect   (TypeDefIndex 5554)
- `HealthFraction` : `float`  `[Range(0, 1)]`

### SpawnBeamEffect : AbilityEffect   (TypeDefIndex 5555)
- `BeamPrefab` : `GameObject`
- `MaxLength` : `float`
- `Width` : `float`
- `TrackTarget` : `bool`
- `TurnSpeed` : `float`
- `FaceBeam` : `bool`
- `FadeOutTime` : `float`
- `OnHitEffects` : `List<AbilityEffect>`  `[SerializeReference]`

### SpawnGroundZoneEffect : AbilityEffect   (TypeDefIndex 5557)
- `value__` : `int`

### SpawnTransientCharacterEffect : AbilityEffect   (TypeDefIndex 5566)
- `value__` : `int`

### StaggeredStrikesEffect : AbilityEffect   (TypeDefIndex 5569)
- `TargetCount` : `int`
- `DelayBetween` : `float`
- `AllowRepeatWhenNoOtherTargets` : `bool`
- `OnHitEffects` : `List<AbilityEffect>`  `[SerializeReference]`

### StatScaledDamageEffect : AbilityEffect   (TypeDefIndex 5570)
- `ScalingStat` : `StatType`
- `MinStatMultiplier` : `float`
- `MaxStatMultiplier` : `float`
- `CanCrit` : `bool`
- `DamageType` : `DamageType`
- `MinMultiplierToken` : `TokenSpec`
- `MaxMultiplierToken` : `TokenSpec`

### StatusEffectData : ScriptableObject   (TypeDefIndex 5595)
- `Icon` : `Sprite`
- `ShowInTooltipExplanation` : `bool`
- `Stackable` : `bool`
- `MaxStacks` : `int`
- `Duration` : `LeveledFloat`
- `DurationToken` : `TokenSpec`
- `TickRate` : `float`
- `PersistAcrossSessions` : `bool`
- `Behaviors` : `List<StatusEffectBehavior>`  `[SerializeReference]`
- `ScaleUpTarget` : `bool`
- `ScalePerStack` : `float`
- `ScaleLerpTime` : `float`
- `AnimatorBool` : `string`
- `PersistentVFXPrefab` : `GameObject`
- `PersistentVFXAnchor` : `VFXAnchor`
- `ApplyColorTint` : `bool`
- `TintColor` : `Color`
- `HpOrbMaterial` : `Material`

### CCDiminishBehavior : StatusEffectBehavior   (TypeDefIndex 5597)
- `DurationMultiplier` : `float`  `[Range(0, 1)]`
- `ResetTime` : `float`

### DamageAmplificationBehavior : StatusEffectBehavior   (TypeDefIndex 5598)
- `AmplificationPercent` : `LeveledFloat`
- `FilterByDamageType` : `bool`
- `AffectedDamageType` : `DamageType`
- `AmplificationToken` : `TokenSpec`

### DamageDealtReductionBehavior : StatusEffectBehavior   (TypeDefIndex 5599)
- `ReductionPercent` : `LeveledFloat`
- `ReductionToken` : `TokenSpec`

### DamageOverTimeBehavior : StatusEffectBehavior   (TypeDefIndex 5601)
- `DamagePerTick` : `float`
- `DamageType` : `DamageType`
- `CanCrit` : `bool`
- `ReapplyMode` : `DotReapplyMode`
- `DamagePerTickToken` : `TokenSpec`

### DamageReductionBehavior : StatusEffectBehavior   (TypeDefIndex 5602)
- `ReductionPercent` : `LeveledFloat`
- `FilterByDamageType` : `bool`
- `AffectedDamageType` : `DamageType`
- `ReductionToken` : `TokenSpec`

### HealOverTimeBehavior : StatusEffectBehavior   (TypeDefIndex 5603)
- `HealPerTick` : `LeveledFloat`
- `HealScaling` : `float`
- `ScaleWithWeaponDamage` : `bool`
- `MaxHealthPercentPerTick` : `LeveledFloat`
- `ReapplyMode` : `DotReapplyMode`
- `ShowHealPopup` : `bool`
- `HealPerTickToken` : `TokenSpec`
- `MaxHealthPercentPerTickToken` : `TokenSpec`

### ImmobilizedBehavior : StatusEffectBehavior   (TypeDefIndex 5604)

### ImmuneBehavior : StatusEffectBehavior   (TypeDefIndex 5605)

### OnEndEffectBehavior : StatusEffectBehavior   (TypeDefIndex 5606)
- `Effects` : `List<AbilityEffect>`  `[SerializeReference]`
- `Radius` : `float`
- `CastVFXPrefab` : `GameObject`
- `CastSFX` : `AudioClip`
- `CastSFXVolume` : `Vector2`
- `CastSFXPitch` : `Vector2`

### PeriodicAreaEffectBehavior : StatusEffectBehavior   (TypeDefIndex 5607)
- `Effects` : `List<AbilityEffect>`  `[SerializeReference]`
- `Radius` : `float`
- `PulseVFXPrefab` : `GameObject`
- `PulseVFXLifetime` : `float`
- `PulseSFX` : `AudioClip`
- `PulseSFXVolume` : `Vector2`
- `PulseSFXPitch` : `Vector2`

### ShieldBehavior : StatusEffectBehavior   (TypeDefIndex 5608)
- `MaxHPPercent` : `LeveledFloat`
- `AddOnReapply` : `bool`
- `MaxHPPercentToken` : `TokenSpec`

### SourceCritChanceBonusBehavior : StatusEffectBehavior   (TypeDefIndex 5609)
- `BonusCritChance` : `float`  `[Range(0, 1)]`
- `BonusCritChanceToken` : `TokenSpec`

### StatModifierBehavior : StatusEffectBehavior   (TypeDefIndex 5610)
- `Modifiers` : `LeveledStatModifier[]`

### StunnedBehavior : StatusEffectBehavior   (TypeDefIndex 5612)

### VulnerableBehavior : StatusEffectBehavior   (TypeDefIndex 5613)

### AudioConfig : ScriptableObject   (TypeDefIndex 5757)
- `Clips` : `List<SoundClip>`
- `MainMenuMusic` : `AudioClip`
- `MainMenuMusicVolume` : `float`  `[Range(0, 1)]`

### EquipmentEffectBehavior : ScriptableObject   (TypeDefIndex 5760)

### EquipmentEffect_AbilityChannelModifier : EquipmentEffectBehavior   (TypeDefIndex 5761)
- `Ability` : `AbilityData`
- `ChannelSpeedBonus` : `float`
- `AdditionalChannelDurationSeconds` : `float`

### EquipmentEffect_AbilityEffectOverride : EquipmentEffectBehavior   (TypeDefIndex 5762)
- `Ability` : `AbilityData`
- `CastsRequired` : `int`
- `OverrideEffects` : `List<AbilityEffect>`  `[SerializeReference]`

### EquipmentEffect_AbilityModifier : EquipmentEffectBehavior   (TypeDefIndex 5763)
- `Tag` : `AbilityTag`
- `Ability` : `AbilityData`
- `Stat` : `TalentEffect_AbilityModifier.ModifiedStat`
- `Modifier` : `float`

### EquipmentEffect_AbilityOnCastCount : EquipmentEffectBehavior   (TypeDefIndex 5764)
- `TrackedTag` : `AbilityTag`
- `TrackedAbility` : `AbilityData`
- `CastsRequired` : `int`
- `TriggeredEffects` : `List<AbilityEffect>`  `[SerializeReference]`
- `TriggerVFXPrefab` : `GameObject`
- `TriggerSFX` : `AudioClip`
- `TriggerSFXVolume` : `Vector2`
- `TriggerSFXPitch` : `Vector2`

### EquipmentEffect_AbilityProjectileCount : EquipmentEffectBehavior   (TypeDefIndex 5765)
- `Ability` : `AbilityData`
- `ExtraProjectiles` : `int`
- `OverrideDegreesBetweenProjectiles` : `bool`
- `DegreesBetweenProjectiles` : `float`

### EquipmentEffect_AbilityProjectileDeflect : EquipmentEffectBehavior   (TypeDefIndex 5767)
- `Ability` : `AbilityData`
- `Deflects` : `int`
- `Targeting` : `DeflectTargeting`

### EquipmentEffect_AbilityProjectileLifetime : EquipmentEffectBehavior   (TypeDefIndex 5768)
- `Ability` : `AbilityData`
- `LifetimeIncrease` : `float`

### EquipmentEffect_AbilityProjectileSize : EquipmentEffectBehavior   (TypeDefIndex 5769)
- `Ability` : `AbilityData`
- `SizeIncrease` : `float`

### EquipmentEffect_AbilitySpawnCount : EquipmentEffectBehavior   (TypeDefIndex 5770)
- `Ability` : `AbilityData`
- `ExtraSpawns` : `int`

### EquipmentEffect_AbilityStrikeSplash : EquipmentEffectBehavior   (TypeDefIndex 5771)
- `Ability` : `AbilityData`
- `Radius` : `float`  `[Min(0)]`

### EquipmentEffect_AbilitySummonAbility : EquipmentEffectBehavior   (TypeDefIndex 5772)
- `SummoningAbility` : `AbilityData`
- `AddedAbility` : `AbilityData`

### EquipmentEffect_AbilityTagApplyStatus : EquipmentEffectBehavior   (TypeDefIndex 5773)
- `Tag` : `AbilityTag`
- `TrackedAbility` : `AbilityData`
- `Target` : `TargetAffinity`
- `StatusEffect` : `StatusEffectData`
- `Chance` : `float`  `[Range(0, 1)]`
- `StacksPerCast` : `int`
- `ConsumeOnCast` : `bool`
- `DamageBonusPerStack` : `float`  `[Min(0)]`

### EquipmentEffect_AbilityTagCritDamage : EquipmentEffectBehavior   (TypeDefIndex 5774)
- `Tag` : `AbilityTag`
- `Ability` : `AbilityData`
- `BonusCritDamage` : `float`

### EquipmentEffect_AbilityTriggerAbility : EquipmentEffectBehavior   (TypeDefIndex 5775)
- `Tag` : `AbilityTag`
- `TrackedAbility` : `AbilityData`
- `TriggeredAbility` : `AbilityData`
- `ProcChance` : `float`  `[Range(0, 1)]`
- `SuppressKnockback` : `bool`

### EquipmentEffect_AllStats : EquipmentEffect_StatModifier   (TypeDefIndex 5777)
- `Bonus` : `float`  `[Min(0)]`

### EquipmentEffect_BeingHitTriggerAbility : EquipmentEffectBehavior   (TypeDefIndex 5778)
- `TriggeredAbility` : `AbilityData`
- `ProcChance` : `float`  `[Range(0, 1)]`
- `DescriptionKey` : `string`

### EquipmentEffect_ChannelAllowedCastTag : EquipmentEffectBehavior   (TypeDefIndex 5779)
- `ChannelAbility` : `AbilityData`
- `AllowedTag` : `AbilityTag`

### EquipmentEffect_ConditionalCritChance : EquipmentEffectBehavior   (TypeDefIndex 5781)
- `Condition` : `TargetStateCondition`
- `BonusCritChance` : `float`  `[Range(0, 1)]`

### EquipmentEffect_ConditionalCritDamage : EquipmentEffectBehavior   (TypeDefIndex 5782)
- `Condition` : `TargetStateCondition`
- `Status` : `StatusEffectData`
- `BonusCritDamage` : `float`

### EquipmentEffect_DamagePerManaFraction : EquipmentEffectBehavior   (TypeDefIndex 5783)
- `MaxBonus` : `float`

### EquipmentEffect_FreeCast : EquipmentEffectBehavior   (TypeDefIndex 5784)
- `Tag` : `AbilityTag`
- `TrackedAbility` : `AbilityData`
- `ProcChance` : `float`  `[Range(0, 1)]`

### EquipmentEffect_GainStatusEverySecond : EquipmentEffectBehavior   (TypeDefIndex 5787)
- `StatusEffect` : `StatusEffectData`
- `Condition` : `StatusGainCondition`
- `Interval` : `float`

### EquipmentEffect_SelfStatusStackTriggerAbility : EquipmentEffectBehavior   (TypeDefIndex 5788)
- `RequiredStatus` : `StatusEffectData`
- `RequiredStacks` : `int`
- `TriggeredAbility` : `AbilityData`
- `SuppressKnockback` : `bool`

### EquipmentEffect_StatConversion : EquipmentEffectBehavior   (TypeDefIndex 5789)
- `SourceStat` : `StatType`
- `TargetStat` : `StatType`
- `Fraction` : `float`

### EquipmentEffect_StatModifier : EquipmentEffectBehavior   (TypeDefIndex 5790)
- `StatModifiers` : `StatModifier[]`
- `RequiredStatus` : `StatusEffectData`
- `SelfCondition` : `PlayerCondition`

### EquipmentEffect_StatPerStatusStack : EquipmentEffectBehavior   (TypeDefIndex 5791)
- `Status` : `StatusEffectData`
- `Stat` : `StatType`
- `ValuePerStack` : `double`

### EquipmentEffect_StatusApplyStatus : EquipmentEffectBehavior   (TypeDefIndex 5792)
- `TriggerStatus` : `StatusEffectData`
- `ResultStatus` : `StatusEffectData`
- `ProcChance` : `float`  `[Range(0, 1)]`

### EquipmentEffect_StatusOnCritTaken : EquipmentEffectBehavior   (TypeDefIndex 5793)
- `StatusEffect` : `StatusEffectData`
- `InternalCooldown` : `float`
- `Chance` : `float`  `[Range(0, 1)]`

### EquipmentEffect_StatusOnHit : EquipmentEffectBehavior   (TypeDefIndex 5794)
- `StatusEffect` : `StatusEffectData`
- `FilterByTag` : `bool`
- `Tag` : `AbilityTag`
- `TrackedAbility` : `AbilityData`
- `Chance` : `float`  `[Range(0, 1)]`
- `StacksPerHit` : `int`
- `GainVFXPrefab` : `GameObject`

### EquipmentEffect_StatusOnKill : EquipmentEffectBehavior   (TypeDefIndex 5795)
- `StatusEffect` : `StatusEffectData`
- `Chance` : `float`  `[Range(0, 1)]`
- `ElitesOnly` : `bool`

### EquipmentEffect_StatusOnLowHealth : EquipmentEffectBehavior   (TypeDefIndex 5796)
- `StatusEffect` : `StatusEffectData`
- `HealthThreshold` : `float`  `[Range(0, 1)]`
- `InternalCooldown` : `float`

### EquipmentEffect_StatusOnResourceConsumed : EquipmentEffectBehavior   (TypeDefIndex 5798)
- `Resource` : `ConsumedResource`
- `Threshold` : `long`
- `StatusEffect` : `StatusEffectData`

### EquipmentEffect_TrapRearm : EquipmentEffectBehavior   (TypeDefIndex 5799)
- `RearmDelay` : `float`  `[Min(0.01)]`
- `MaxRearms` : `int`  `[Min(0)]`

### EquipmentEffect_TriggerAbilityCooldownReduction : EquipmentEffectBehavior   (TypeDefIndex 5800)
- `Tag` : `AbilityTag`
- `TrackedAbility` : `AbilityData`
- `TargetAbility` : `AbilityData`
- `TargetTag` : `AbilityTag`
- `RandomSingleTarget` : `bool`
- `ReductionSeconds` : `float`
- `ProcChance` : `float`  `[Range(0, 1),FormerlySerializedAs("ResetChance")]`

### EquipmentEffect_TriggerAbilityTwice : EquipmentEffectBehavior   (TypeDefIndex 5801)
- `Tag` : `AbilityTag`
- `TrackedAbility` : `AbilityData`
- `ProcChance` : `float`  `[Range(0, 1)]`

### EquipmentEffect_TriggerDotDetonation : EquipmentEffectBehavior   (TypeDefIndex 5804)
- `Tag` : `AbilityTag`
- `TrackedAbility` : `AbilityData`
- `DotFilter` : `StatusEffectData`
- `Timing` : `DotDetonateTiming`
- `Chance` : `float`  `[Range(0, 1)]`
- `ImpactVFXPrefab` : `GameObject`

### EquipmentEffect_TriggerEffectsOnCrit : EquipmentEffectBehavior   (TypeDefIndex 5805)
- `Ability` : `AbilityData`
- `Tag` : `AbilityTag`
- `TriggeredEffects` : `List<AbilityEffect>`  `[SerializeReference]`
- `Chance` : `float`  `[Range(0, 1)]`
- `InternalCooldown` : `float`

### EquipmentEffect_TriggerEffectsOnHit : EquipmentEffectBehavior   (TypeDefIndex 5806)
- `Tag` : `AbilityTag`
- `TriggeredEffects` : `List<AbilityEffect>`  `[SerializeReference]`
- `Chance` : `float`  `[Range(0, 1)]`
- `DescriptionKey` : `string`

### EquipmentEffect_TriggerEffectsOnPotionUse : EquipmentEffectBehavior   (TypeDefIndex 5807)
- `TriggeredEffects` : `List<AbilityEffect>`  `[SerializeReference]`
- `Chance` : `float`  `[Range(0, 1)]`

### EquipmentEffect_TriggerKillEffectsOnHit : EquipmentEffectBehavior   (TypeDefIndex 5808)
- `Chance` : `float`  `[Range(0, 1)]`
- `DescriptionKey` : `string`

### TriggerEffectOnStatus : EquipmentEffectBehavior   (TypeDefIndex 5811)
- `TriggerStatus` : `StatusEffectData`
- `Mode` : `StatusTriggerMode`
- `Interval` : `float`
- `TriggeredEffects` : `List<AbilityEffect>`  `[SerializeReference]`
- `TriggerVFXPrefab` : `GameObject`
- `TriggerSFX` : `AudioClip`
- `TriggerSFXVolume` : `Vector2`
- `TriggerSFXPitch` : `Vector2`

### FishingMapData : ScriptableObject   (TypeDefIndex 5815)
- `Wait` : `float`
- `Item` : `ItemData`

### GameConfig : ScriptableObject   (TypeDefIndex 5822)
- `DlcSlave` : `SlaveData`
- `DlcBackEquipment` : `ItemData`
- `IsDemo` : `bool`
- `InteractableLayer` : `LayerMask`
- `GroundLayerMask` : `LayerMask`
- `PotionUpgradeData` : `HealingPotionUpgradeData`
- `Itemization` : `ItemizationConfig`
- `Loot` : `LootConfig`
- `UpgradeRecipes` : `EquipmentUpgradeRecipe[]`
- `ExtraUpgradeMaterials` : `EquipmenSlotUpgradeMaterial[]`
- `SpecialUpgradeRecipe` : `RecipeData`
- `MaxEquipmentUpgradeLevel` : `int`
- `SocketMaterial` : `ItemData`
- `SocketMaterialAmount` : `int`
- `SocketGoldPerItemLevel` : `int`
- `SalvageYields` : `SalvageYield[]`
- `UpgradeSuccessChances` : `float[]`  `[Range(0, 1)]`
- `GatherableConfigs` : `GatherableTypeConfig[]`
- `TalentRefundCostPerPointSpent` : `int`
- `EliteHealthMultiplier` : `float`
- `EliteDamageMultiplier` : `float`
- `EliteScaleMultiplier` : `float`
- `BossTenacityStatus` : `StatusEffectData`
- `MythicBossEnrageCountdownStatus` : `StatusEffectData`
- `MythicBossEnragedStatus` : `StatusEffectData`
- `DifficultyTiers` : `DifficultyTierConfig[]`
- `WorldFinalBossMap` : `MapData`
- `MinMythicDifficulty` : `WorldDifficulty`
- `EnemyHealthGrowthPerLevel0To30` : `float`
- `EnemyDamageGrowthPerLevel0To30` : `float`
- `EnemyHealthGrowthPerLevel31To50` : `float`
- `EnemyDamageGrowthPerLevel31To50` : `float`
- `EnemyHealthGrowthPerLevel51To70` : `float`
- `EnemyDamageGrowthPerLevel51To70` : `float`
- `MobsToLevelAtLevel1` : `int`
- `MobsToLevelAtLevel5` : `int`
- `MobsToLevelAtLevel15` : `int`
- `MobsToLevelAtLevel50` : `int`
- `MobsToLevelAtMaxLevel` : `int`
- `MaxPlayerLevel` : `int`
- `XpPerBaseHealth` : `float`
- `XpPerLevelScale` : `float`
- `XpZeroUnderLevel` : `int`
- `ParagonMobsToLevelKnots` : `Vector2Int[]`
- `ParagonMobsGrowthPastLastKnot` : `int`
- `ParagonPointsPerLevel` : `int`
- `ParagonStats` : `ParagonStat[]`
- `OfflineMobsPerHourKnots` : `Vector2Int[]`
- `OfflineMobsPerGoldRoll` : `float`  `[Min(0.01)]`
- `OfflineTimeCapHours` : `float`
- `MaxAbilityLevel` : `int`
- `AbilityBaseXPToLevel` : `long`
- `AbilityXPGrowthPerLevel` : `float`
- `RuneSlotUnlockLevels` : `int[]`
- `MaxRuneLevel` : `int`
- `RuneBaseXPToLevel` : `long`
- `RuneXPGrowthPerLevel` : `float`

### GemData : ItemData   (TypeDefIndex 5824)
- `Stat` : `StatType`
- `Modifier` : `ModifierType`
- `Value` : `float`

### GraphicsConfig : ScriptableObject   (TypeDefIndex 5826)
- `TitleFont` : `TMP_FontAsset`
- `SubtitleFont` : `TMP_FontAsset`
- `ParagraphFont` : `TMP_FontAsset`

### HealingPotionUpgradeData : ScriptableObject   (TypeDefIndex 5830)
- `Tiers` : `HealingPotionUpgradeTier[]`

### HeroData : ScriptableObject   (TypeDefIndex 5833)
- `HeroName` : `string`
- `Icon` : `Sprite`
- `IsLockedInDemo` : `bool`
- `PrimaryStat` : `PrimaryStat`
- `Class` : `HeroClass`
- `StartingWeapon` : `ItemData`
- `CharacterPrefab` : `GameObject`
- `DeathSound` : `SimpleSound`
- `Abilities` : `List<AbilityData>`

### ItemData : ScriptableObject   (TypeDefIndex 5839)
- `Icon` : `Sprite`
- `Type` : `ItemType`
- `Rarity` : `ItemRarity`
- `SellPrice` : `int`
- `MinDropLevel` : `int`
- `MaxDropLevel` : `int`
- `Effect` : `ItemEffect`
- `SlaveToUnlock` : `SlaveData`
- `BuffEffect` : `StatusEffectData`
- `BuffCategory` : `BuffCategory`
- `ChestMinDrops` : `int`
- `ChestMaxDrops` : `int`
- `ChestCommonChance` : `float`
- `ChestUncommonChance` : `float`
- `ChestRareChance` : `float`
- `ChestLegendaryChance` : `float`
- `ChestDivineChance` : `float`  `[Range(0, 1)]`
- `ChestGemChance` : `float`  `[Range(0, 1)]`
- `ChestGoldMin` : `int`
- `ChestGoldMax` : `int`
- `UseVfxPrefab` : `GameObject`
- `HasUseSfx` : `bool`
- `UseSfx` : `AudioClipEnum`
- `MaxStackSize` : `int`
- `MaxCarry` : `int`
- `EquipSlot` : `EquipSlotType`
- `NotUpgradable` : `bool`
- `UsableClasses` : `HeroClass`
- `WeaponModelPrefab` : `GameObject`
- `BackModelPrefab` : `GameObject`
- `EquipmentEffects` : `EquipmentEffectBehavior[]`
- `AbilityLevels` : `AbilityLevelGrant[]`
- `FixedStats` : `StatModifier[]`
- `SteamItemDefId` : `int`
- `SteamRetired` : `bool`
- `BlackMistSteamItemDefId` : `int`

### ItemizationConfig : ScriptableObject   (TypeDefIndex 5842)
- `SlotPools` : `List<SlotAffixPool>`
- `GemSocketsBySlot` : `List<SlotSocketConfig>`
- `MinLevelForSockets` : `int`

### LifeSkillEffect_FeatureFlag : LifeSkillNodeEffect   (TypeDefIndex 5843)
- `Features` : `LifeSkillFeature[]`

### LifeSkillEffect_FishingSuccess : LifeSkillNodeEffect   (TypeDefIndex 5844)
- `SuccessBonus` : `float`
- `Token` : `TokenSpec`

### LifeSkillEffect_FishingTime : LifeSkillNodeEffect   (TypeDefIndex 5845)
- `TimeReduction` : `float`
- `Token` : `TokenSpec`

### LifeSkillEffect_MaterialCarryCap : LifeSkillNodeEffect   (TypeDefIndex 5846)
- `Material` : `ItemData`
- `CapAdded` : `int`
- `Token` : `TokenSpec`

### LifeSkillEffect_OfflineTimeCap : LifeSkillNodeEffect   (TypeDefIndex 5847)
- `HoursAdded` : `float`
- `Token` : `TokenSpec`

### LifeSkillEffect_ReviveCooldown : LifeSkillNodeEffect   (TypeDefIndex 5848)
- `SecondsReduced` : `LeveledFloat`
- `Token` : `TokenSpec`

### LifeSkillEffect_StatModifier : LifeSkillNodeEffect   (TypeDefIndex 5849)
- `StatModifiers` : `LeveledStatModifier[]`

### LifeSkillEffect_UnlockConsumableSlot : LifeSkillNodeEffect   (TypeDefIndex 5850)
- `Category` : `BuffCategory`

### LifeSkillEffect_UnlockStoragePage : LifeSkillNodeEffect   (TypeDefIndex 5851)
- `Pages` : `int`

### LifeSkillNodeData : ScriptableObject   (TypeDefIndex 5853)
- `Icon` : `Sprite`
- `MaxLevel` : `int`  `[Min(1)]`
- `GoldCosts` : `int[]`
- `Prerequisite` : `LifeSkillNodeData`
- `IsLockedInDemo` : `bool`
- `Effects` : `LifeSkillNodeEffect[]`
- `IsNotable` : `bool`

### LifeSkillNodeEffect : ScriptableObject   (TypeDefIndex 5854)

### LootConfig : ScriptableObject   (TypeDefIndex 5861)
- `PotionChargeDropChance` : `float`  `[Range(0, 1)]`
- `GoldDropChance` : `float`  `[Range(0, 1)]`
- `GoldMultiplier` : `float`
- `RollAttempts` : `int`
- `MinLootVector` : `LootConfig.LootVector`
- `MaxLootVector` : `LootConfig.LootVector`
- `DivineChance` : `float`  `[Range(0, 1)]`
- `GemDropChance` : `float`  `[Range(0, 1)]`

### LuckyWheelData : ScriptableObject   (TypeDefIndex 5863)
- `Prerequisite` : `MapData`
- `IsLockedInDemo` : `bool`
- `IsUnavailable` : `bool`
- `WheelPrefab` : `GameObject`
- `SpinCost` : `int`  `[Min(1)]`
- `Segments` : `WheelSegment[]`

### MapData : ScriptableObject   (TypeDefIndex 5870)
- `Prerequisite` : `MapData`
- `MapType` : `CombatMapType`  `[FormerlySerializedAs("IsMythic")]`
- `EnemyMinLevel` : `int`
- `EnemyMaxLevel` : `int`
- `IsLockedInDemo` : `bool`
- `IsUnavailable` : `bool`
- `EntryRequirements` : `MapEntryRequirement[]`
- `MaxEncounters` : `int`
- `EliteChance` : `float`  `[Range(0, 1)]`
- `NormalEncounterPool` : `EncounterData[]`
- `IsMiniBoss` : `bool`
- `BossEncounter` : `EncounterData`
- `CompletionCutscene` : `Cutscene`
- `SummaryBackground` : `Sprite`
- `GroundTilePrefabs` : `GameObject[]`
- `LightingPrefab` : `GameObject`
- `GatherableMeanPerTile` : `float`  `[Min(0)]`
- `_gatherablePoissonPreview` : `string`  `[TextArea(4, 14),SerializeField]`
- `Gatherables` : `GatherableSpawnEntry[]`
- `MythicBaseHP` : `long`
- `MythicBaseDamage` : `long`
- `MythicBossBaseHP` : `long`
- `MythicBossBaseDamage` : `long`
- `MythicBand1EndTier` : `int`  `[Range(0, 99)]`
- `MythicBand1HealthMultiplierPerTier` : `float`
- `MythicBand1DamageMultiplierPerTier` : `float`
- `MythicBand2HealthMultiplierPerTier` : `float`
- `MythicBand2DamageMultiplierPerTier` : `float`
- `MythicGoldBonusPerTier` : `float`  `[Min(0)]`
- `MythicExpBonusPerTier` : `float`  `[Min(0)]`
- `MythicNormalEnemies` : `GameObject[]`
- `MythicBossEnemies` : `GameObject[]`
- `MythicMinEnemiesPerEncounter` : `int`  `[Min(1)]`
- `MythicMaxEnemiesPerEncounter` : `int`  `[Min(1)]`
- `MythicMinEnemyTypesPerRun` : `int`  `[Min(1)]`
- `MythicMaxEnemyTypesPerRun` : `int`  `[Min(1)]`
- `MythicZones` : `MythicZone[]`
- `MusicClip` : `AudioClip`
- `MusicVolume` : `float`  `[Range(0, 1)]`
- `MusicClip2` : `AudioClip`
- `MusicVolume2` : `float`  `[Range(0, 1)]`

### QuestData : ScriptableObject   (TypeDefIndex 5874)
- `Requirements` : `QuestRequirement[]`
- `Dialogue` : `string`  `[TextArea(2, 5)]`
- `DialogueArgs` : `QuestDialogueArg[]`

### RandomEquipment : ItemData   (TypeDefIndex 5875)
- `Slot` : `EquipSlotType`

### RecipeBook : ScriptableObject   (TypeDefIndex 5876)
- `Recipes` : `RecipeData[]`

### RecipeData : ScriptableObject   (TypeDefIndex 5878)
- `Ingredients` : `CraftingIngredient[]`
- `OutputItem` : `ItemData`
- `OutputQuantity` : `int`
- `GoldCost` : `int`
- `IsLockedInDemo` : `bool`

### RuneData : ItemData   (TypeDefIndex 5880)
- `Stat` : `StatType`
- `Modifier` : `ModifierType`
- `Value` : `LeveledFloat`

### RuneSetData : ScriptableObject   (TypeDefIndex 5882)
- `RequiredCount` : `int`
- `Modifiers` : `StatModifier[]`
- `Effects` : `EquipmentEffectBehavior[]`
- `AbilityLevels` : `AbilityLevelGrant[]`

### SlaveData : ScriptableObject   (TypeDefIndex 5884)
- `Species` : `SlaveSpecies`
- `Rarity` : `ItemRarity`
- `IsLockedInDemo` : `bool`
- `Location` : `string`
- `Capacity` : `int`
- `Prefab` : `GameObject`
- `SummonSound` : `SimpleSound`
- `ZoomOutDistance` : `float`
- `RunAnimSpeedMultiplier` : `float`
- `Passives` : `SlavePassive[]`
- `Abilities` : `AbilityData[]`

### TalentData : ScriptableObject   (TypeDefIndex 5886)
- `Icon` : `Sprite`
- `MaxPoints` : `int`
- `LevelRequirement` : `int`
- `Prerequisite` : `TalentData`
- `ExclusiveGroup` : `string`
- `IsLockedInDemo` : `bool`
- `StatModifiers` : `LeveledStatModifier[]`
- `Effects` : `TalentEffectBehavior[]`

### TalentEffectBehavior : ScriptableObject   (TypeDefIndex 5887)

### TalentEffect_AbilityAddNthCastEffect : TalentEffectBehavior   (TypeDefIndex 5889)
- `Ability` : `AbilityData`
- `ScalePayloadByPoints` : `bool`
- `EffectsToAdd` : `List<AbilityEffect>`  `[SerializeReference]`

### TalentEffect_AbilityAoEApplyStatus : TalentEffectBehavior   (TypeDefIndex 5890)
- `Ability` : `AbilityData`
- `StatusEffect` : `StatusEffectData`
- `Chance` : `LeveledFloat`
- `ChanceToken` : `TokenSpec`

### TalentEffect_AbilityApplyStatus : TalentEffectBehavior   (TypeDefIndex 5891)
- `Ability` : `AbilityData`
- `Tag` : `AbilityTag`
- `Target` : `TargetAffinity`
- `RequireDirectHit` : `bool`
- `StatusEffect` : `StatusEffectData`
- `ScaleStatusByPoints` : `bool`
- `Chance` : `LeveledFloat`
- `ChanceToken` : `TokenSpec`
- `StacksPerCast` : `LeveledFloat`
- `StacksPerCastToken` : `TokenSpec`

### TalentEffect_AbilityExecute : TalentEffectBehavior   (TypeDefIndex 5892)
- `Ability` : `AbilityData`
- `Tag` : `AbilityTag`
- `Chance` : `LeveledFloat`
- `ChanceToken` : `TokenSpec`
- `HealthThreshold` : `double`
- `HealthThresholdToken` : `TokenSpec`

### TalentEffect_AbilityHitStackBuff : TalentEffectBehavior   (TypeDefIndex 5893)
- `Tag` : `AbilityTag`
- `StackStatus` : `StatusEffectData`
- `BuffStatus` : `StatusEffectData`
- `StacksToken` : `TokenSpec`

### TalentEffect_AbilityKnockback : TalentEffectBehavior   (TypeDefIndex 5894)
- `Ability` : `AbilityData`
- `Tag` : `AbilityTag`
- `Chance` : `LeveledFloat`
- `ChanceToken` : `TokenSpec`
- `Distance` : `LeveledFloat`
- `DistanceToken` : `TokenSpec`

### TalentEffect_AbilityModifier : TalentEffectBehavior   (TypeDefIndex 5896)
- `value__` : `int`

### TalentEffect_AbilityProjectilePierceDamage : TalentEffectBehavior   (TypeDefIndex 5897)
- `Ability` : `AbilityData`
- `DamageIncrease` : `LeveledFloat`
- `DamageIncreaseToken` : `TokenSpec`

### TalentEffect_AbilityProjectileRicochet : TalentEffectBehavior   (TypeDefIndex 5898)
- `Ability` : `AbilityData`
- `Ricochets` : `int`  `[Min(1)]`

### TalentEffect_AbilityProjectileSpeed : TalentEffectBehavior   (TypeDefIndex 5899)
- `Ability` : `AbilityData`
- `SpeedIncrease` : `LeveledFloat`
- `SpeedIncreaseToken` : `TokenSpec`

### TalentEffect_AbilityTriggerAbility : TalentEffectBehavior   (TypeDefIndex 5900)
- `Ability` : `AbilityData`
- `Tag` : `AbilityTag`
- `TriggeredAbility` : `AbilityData`
- `UseTalentLevel` : `bool`
- `Chance` : `LeveledFloat`
- `ChanceToken` : `TokenSpec`

### TalentEffect_ActiveSlaveBonus : TalentEffectBehavior   (TypeDefIndex 5901)
- `RequiredSpecies` : `SlaveSpecies`
- `Bonuses` : `LeveledStatModifier[]`

### TalentEffect_AlternatingAbilityMana : TalentEffectBehavior   (TypeDefIndex 5902)
- `Tag` : `AbilityTag`
- `PercentMaxMana` : `LeveledFloat`
- `PercentMaxManaToken` : `TokenSpec`

### TalentEffect_BleedDeathBurst : TalentEffectBehavior   (TypeDefIndex 5903)
- `DamageFraction` : `LeveledFloat`
- `Radius` : `float`
- `DamageFractionToken` : `TokenSpec`
- `RadiusToken` : `TokenSpec`

### TalentEffect_CastSequenceDamage : TalentEffectBehavior   (TypeDefIndex 5904)
- `CountTag` : `AbilityTag`
- `CastsRequired` : `int`  `[Min(1)]`
- `EmpowerTag` : `AbilityTag`
- `BankCharges` : `bool`
- `DirectDamageOnly` : `bool`
- `DamageBonus` : `LeveledFloat`
- `DamageBonusToken` : `TokenSpec`
- `CastsToken` : `TokenSpec`
- `ChargeStatus` : `StatusEffectData`

### TalentEffect_CheatDeath : TalentEffectBehavior   (TypeDefIndex 5905)
- `HealPercent` : `LeveledFloat`
- `HealPercentToken` : `TokenSpec`
- `Cooldown` : `LeveledFloat`
- `CooldownToken` : `TokenSpec`
- `TriggerVFXPrefab` : `GameObject`
- `StatusAfterPrevent` : `StatusEffectData`

### TalentEffect_ConditionalBonusDamage : TalentEffectBehavior   (TypeDefIndex 5906)
- `RequiredStatus` : `StatusEffectData`
- `Ability` : `AbilityData`
- `Tag` : `AbilityTag`
- `RequireOnSelf` : `bool`
- `BonusDamage` : `LeveledFloat`
- `BonusDamageToken` : `TokenSpec`

### TalentEffect_ConditionalCritChance : TalentEffectBehavior   (TypeDefIndex 5907)
- `Condition` : `TargetStateCondition`
- `Ability` : `AbilityData`
- `Tag` : `AbilityTag`
- `SpecifiedStatus` : `StatusEffectData`
- `BonusCritChance` : `LeveledFloat`
- `BonusCritChanceToken` : `TokenSpec`

### TalentEffect_ConditionalCritDamage : TalentEffectBehavior   (TypeDefIndex 5908)
- `Condition` : `TargetStateCondition`
- `SpecifiedStatus` : `StatusEffectData`
- `BonusCritDamage` : `LeveledFloat`
- `BonusCritDamageToken` : `TokenSpec`

### TalentEffect_ConditionalStat : TalentEffectBehavior   (TypeDefIndex 5909)
- `Condition` : `PlayerCondition`
- `ChannelingAbility` : `AbilityData`
- `Radius` : `float`  `[Min(0)]`
- `Modifiers` : `LeveledStatModifier[]`

### TalentEffect_CritTriggerEffect : TalentEffectBehavior   (TypeDefIndex 5911)
- `value__` : `int`

### TalentEffect_DodgeTriggerEffect : TalentEffectBehavior   (TypeDefIndex 5912)
- `ProcChance` : `LeveledFloat`
- `TriggeredEffects` : `List<AbilityEffect>`  `[SerializeReference]`
- `ProcChanceToken` : `TokenSpec`

### TalentEffect_DotTickLifeOnHit : TalentEffectBehavior   (TypeDefIndex 5913)
- `RequiredDamageType` : `DamageType`
- `Chance` : `LeveledFloat`
- `ChanceToken` : `TokenSpec`

### TalentEffect_HitsTakenTriggerEffect : TalentEffectBehavior   (TypeDefIndex 5915)
- `value__` : `int`

### TalentEffect_LowHPHeal : TalentEffectBehavior   (TypeDefIndex 5916)
- `HealPercent` : `LeveledFloat`
- `HealPercentToken` : `TokenSpec`
- `HPThreshold` : `float`  `[Range(0.01, 0.99)]`
- `Cooldown` : `float`

### TalentEffect_LowHPTriggerEffect : TalentEffectBehavior   (TypeDefIndex 5917)
- `HPThreshold` : `float`  `[Range(0.01, 0.99)]`
- `Radius` : `float`  `[Min(0)]`
- `Cooldown` : `float`  `[Min(0)]`
- `TriggeredEffects` : `List<AbilityEffect>`  `[SerializeReference]`
- `HPThresholdToken` : `TokenSpec`
- `RadiusToken` : `TokenSpec`
- `CooldownToken` : `TokenSpec`

### TalentEffect_ManaSpentTriggerEffect : TalentEffectBehavior   (TypeDefIndex 5918)
- `TriggeredEffects` : `List<AbilityEffect>`  `[SerializeReference]`

### TalentEffect_ManaUpkeepStatus : TalentEffectBehavior   (TypeDefIndex 5920)
- `StatusEffect` : `StatusEffectData`
- `MaxManaPercent` : `float`  `[Range(0, 1)]`
- `Interval` : `float`  `[Min(0.01)]`
- `MaxManaPercentToken` : `TokenSpec`

### TalentEffect_NthAbilityApplyStatus : TalentEffectBehavior   (TypeDefIndex 5922)
- `Tag` : `AbilityTag`
- `BaseCastInterval` : `int`  `[Min(1)]`
- `CastIntervalReductionPerPoint` : `int`  `[Min(0)]`
- `MinimumCastInterval` : `int`  `[Min(1)]`
- `CastIntervalToken` : `TokenSpec`
- `StatusEffect` : `StatusEffectData`
- `RequireDirectHit` : `bool`
- `OncePerTargetPerCast` : `bool`

### TalentEffect_OnKillTriggerEffect : TalentEffectBehavior   (TypeDefIndex 5923)
- `Ability` : `AbilityData`
- `Tag` : `AbilityTag`
- `RequiredVictimStatus` : `StatusEffectData`
- `Target` : `TargetAffinity`
- `Radius` : `LeveledFloat`
- `Chance` : `LeveledFloat`
- `AllowChainReactions` : `bool`
- `ScalePayloadByPoints` : `bool`
- `CastVFXPrefab` : `GameObject`
- `CastSFX` : `AudioClip`
- `CastSFXVolume` : `Vector2`
- `CastSFXPitch` : `Vector2`
- `TriggeredEffects` : `List<AbilityEffect>`  `[SerializeReference]`
- `RadiusToken` : `TokenSpec`
- `ChanceToken` : `TokenSpec`

### TalentEffect_RemainingManaDamage : TalentEffectBehavior   (TypeDefIndex 5924)
- `Tag` : `AbilityTag`
- `DamagePerMana` : `LeveledFloat`
- `DamagePerManaToken` : `TokenSpec`

### TalentEffect_StatConversion : TalentEffectBehavior   (TypeDefIndex 5925)
- `SourceStat` : `StatType`
- `TargetStat` : `StatType`
- `Fraction` : `LeveledFloat`
- `FractionToken` : `TokenSpec`
- `RequiredStatus` : `StatusEffectData`

### TalentEffect_StatusApplyStatus : TalentEffectBehavior   (TypeDefIndex 5926)
- `TriggerStatus` : `StatusEffectData`
- `ResultStatus` : `StatusEffectData`
- `ProcChance` : `LeveledFloat`
- `ProcChanceToken` : `TokenSpec`

### TalentEffect_StatusPotency : TalentEffectBehavior   (TypeDefIndex 5927)
- `Status` : `StatusEffectData`
- `PotencyBonus` : `LeveledFloat`
- `DurationBonus` : `LeveledFloat`
- `FlatDurationBonus` : `LeveledFloat`
- `PotencyToken` : `TokenSpec`
- `DurationToken` : `TokenSpec`
- `FlatDurationToken` : `TokenSpec`

### TalentEffect_StatusStackTriggerEffect : TalentEffectBehavior   (TypeDefIndex 5928)
- `Ability` : `AbilityData`
- `Tag` : `AbilityTag`
- `RequiredStatus` : `StatusEffectData`
- `RequiredStacks` : `int`
- `TriggeredEffects` : `List<AbilityEffect>`  `[SerializeReference]`
- `TriggerVFXPrefab` : `GameObject`
- `TriggerSFX` : `AudioClip`

### TalentEffect_StatusStatBonus : TalentEffectBehavior   (TypeDefIndex 5929)
- `Status` : `StatusEffectData`
- `Modifiers` : `LeveledStatModifier[]`

### TalentEffect_ThornsCanCrit : TalentEffectBehavior   (TypeDefIndex 5930)

### TalentEffect_TriggerAbilityCooldownReduction : TalentEffectBehavior   (TypeDefIndex 5932)
- `value__` : `int`

### TalentEffect_TriggerAbilityTwice : TalentEffectBehavior   (TypeDefIndex 5933)
- `Tag` : `AbilityTag`
- `TrackedAbility` : `AbilityData`
- `Chance` : `LeveledFloat`
- `ChanceToken` : `TokenSpec`
- `Delay` : `float`  `[Range(0, 1)]`

### TownData : ScriptableObject   (TypeDefIndex 5934)
- `Prerequisite` : `MapData`
- `IsLockedInDemo` : `bool`
- `TownPrefab` : `GameObject`
- `MusicClip` : `AudioClip`
- `MusicVolume` : `float`  `[Range(0, 1)]`
- `MusicClip2` : `AudioClip`
- `MusicVolume2` : `float`  `[Range(0, 1)]`

### Enemy : Character   (TypeDefIndex 5943)
- `MinEnemySpacing` : `float`
- `HighDifficultyHpOverride` : `long`
- `HighDifficultyDmgOverride` : `long`
- `MythicSize` : `MythicEnemySize`
- `Abilities` : `AbilityData[]`
- `Phases` : `EnemyPhase[]`
- `AbilitySound` : `SimpleSound`
- `AbilitySoundChance` : `float`  `[Range(0, 1)]`
- `DropsLoot` : `bool`
- `SpecialDrops` : `EnemySpecialDropEntry[]`


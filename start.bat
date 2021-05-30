@echo off
TITLE ArchivistsBot
:: Enables virtual env mode and then starts ArchivistsBot
env\scripts\activate.bat && py -m bot

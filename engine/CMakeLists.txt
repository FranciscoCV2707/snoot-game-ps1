cmake_minimum_required(VERSION 3.21)

project(
	snoot
	LANGUAGES    C ASM
	VERSION      0.1.0
	DESCRIPTION  "Snoot Game para PlayStation 1"
)

file(GLOB _sources CONFIGURE_DEPENDS src/*.c)
psn00bsdk_add_executable(snoot GPREL ${_sources})
target_include_directories(snoot PRIVATE include)

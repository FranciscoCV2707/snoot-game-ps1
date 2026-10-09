cmake_minimum_required(VERSION 3.21)

project(
	xa_test
	LANGUAGES    C ASM
	VERSION      1.0.0
	DESCRIPTION  "Prueba XA + carga de datos del CD"
)

psn00bsdk_add_executable(xa_test GPREL main.c)

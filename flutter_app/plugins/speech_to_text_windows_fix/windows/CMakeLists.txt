cmake_minimum_required(VERSION 3.14)
set(PROJECT_NAME "speech_to_text_windows")
project(${PROJECT_NAME} LANGUAGES CXX)

set(PLUGIN_NAME "speech_to_text_windows_plugin")

add_library(${PLUGIN_NAME} SHARED
  "include/speech_to_text_windows/speech_to_text_windows.h"
  "speech_to_text_windows.cpp"
  "speech_to_text_windows_plugin.cpp"
  "speech_to_text_windows_plugin.h"
)

apply_standard_settings(${PLUGIN_NAME})
set_property(TARGET ${PLUGIN_NAME} PROPERTY CXX_STANDARD 17)
set_property(TARGET ${PLUGIN_NAME} PROPERTY CXX_STANDARD_REQUIRED ON)
set_target_properties(${PLUGIN_NAME} PROPERTIES CXX_VISIBILITY_PRESET hidden)

target_compile_definitions(${PLUGIN_NAME} PRIVATE
  FLUTTER_PLUGIN_IMPL
  WIN32_LEAN_AND_MEAN
  NOMINMAX
  _CRT_SECURE_NO_WARNINGS
  _WINSOCK_DEPRECATED_NO_WARNINGS
)

if(MSVC)
  target_compile_options(${PLUGIN_NAME} PRIVATE /wd4996 /wd4245 /W3)
endif()

# PUBLIC so the runner can find the header for the registrant
target_include_directories(${PLUGIN_NAME} PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}/include"
)

target_link_libraries(${PLUGIN_NAME} PRIVATE
  flutter
  flutter_wrapper_plugin
  ole32
  oleaut32
  uuid
  sapi
)

set(speech_to_text_windows_bundled_libraries "" PARENT_SCOPE)

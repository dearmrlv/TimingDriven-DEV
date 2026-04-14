cmake_minimum_required(VERSION 3.0.2)

project(test)

install(
    DIRECTORY iccad2015.ot DESTINATION ${PROJECT_NAME}
    )

install(
    DIRECTORY iccad2015.pin2pin DESTINATION ${PROJECT_NAME}
    )

install(
    DIRECTORY iccad2015.dcf DESTINATION ${PROJECT_NAME}
    )

install(
    DIRECTORY iccad2015.dcfv3 DESTINATION ${PROJECT_NAME}
    )

install(
    DIRECTORY iccad2015.diagnostics DESTINATION ${PROJECT_NAME}
    )

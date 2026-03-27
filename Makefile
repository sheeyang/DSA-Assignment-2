CXX = g++
CXXFLAGS = -std=c++17 -O2 -Wall -Wextra
TARGET = simplify
SRC = simplify.cpp

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SRC)

clean:
	rm -f $(TARGET)

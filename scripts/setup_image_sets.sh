#!/bin/bash

# setup_image_sets.sh - Helper script to set up image sets for multi-reconstruction pipeline
# 
# This script helps with two tasks:
# 1. Moving images from the input folder to a named image set
# 2. Creating a new image set directory

set -e  # Exit on error

# Default paths
INPUT_DIR="input"
IMAGE_SETS_DIR="image_sets"

# Show help message
show_help() {
    echo "Usage: $0 [OPTIONS] COMMAND"
    echo ""
    echo "Commands:"
    echo "  move-input SET_NAME  Move all images from input/ to image_sets/SET_NAME/"
    echo "  create-set SET_NAME  Create an empty directory for a new image set"
    echo "  list                 List all current image sets"
    echo ""
    echo "Options:"
    echo "  -h, --help           Show this help message"
    echo "  -i, --input DIR      Specify input directory (default: ./input)"
    echo "  -s, --sets DIR       Specify image sets directory (default: ./image_sets)"
    echo ""
    echo "Examples:"
    echo "  $0 move-input house_front    # Move images from input/ to image_sets/house_front/"
    echo "  $0 create-set statue         # Create an empty directory at image_sets/statue/"
    echo "  $0 list                      # List all current image sets"
    echo ""
}

# Parse command line options
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -i|--input)
            INPUT_DIR="$2"
            shift
            ;;
        -s|--sets)
            IMAGE_SETS_DIR="$2"
            shift
            ;;
        move-input|create-set|list)
            COMMAND="$1"
            if [[ "$1" != "list" ]]; then
                SET_NAME="$2"
                shift
            fi
            ;;
        *)
            if [[ -z "$COMMAND" ]]; then
                echo "Error: Unknown command '$1'"
                show_help
                exit 1
            elif [[ "$COMMAND" != "list" && -z "$SET_NAME" ]]; then
                SET_NAME="$1"
            else
                echo "Error: Unexpected argument '$1'"
                show_help
                exit 1
            fi
            ;;
    esac
    shift
done

# Create image_sets directory if it doesn't exist
if [[ ! -d "$IMAGE_SETS_DIR" ]]; then
    echo "Creating image sets directory: $IMAGE_SETS_DIR"
    mkdir -p "$IMAGE_SETS_DIR"
fi

# Execute the command
case $COMMAND in
    move-input)
        if [[ -z "$SET_NAME" ]]; then
            echo "Error: No set name provided"
            show_help
            exit 1
        fi
        
        # Create the target directory
        TARGET_DIR="$IMAGE_SETS_DIR/$SET_NAME"
        mkdir -p "$TARGET_DIR"
        
        # Check if the input directory exists and has images
        if [[ ! -d "$INPUT_DIR" ]]; then
            echo "Error: Input directory '$INPUT_DIR' does not exist"
            exit 1
        fi
        
        IMG_COUNT=$(find "$INPUT_DIR" -maxdepth 1 -type f \( -name "*.jpg" -o -name "*.png" \) | wc -l)
        if [[ $IMG_COUNT -eq 0 ]]; then
            echo "Error: No images found in '$INPUT_DIR'"
            exit 1
        fi
        
        # Move the images
        echo "Moving $IMG_COUNT images from '$INPUT_DIR' to '$TARGET_DIR'..."
        find "$INPUT_DIR" -maxdepth 1 -type f \( -name "*.jpg" -o -name "*.png" \) -exec mv {} "$TARGET_DIR/" \;
        
        echo "Done! Images moved to '$TARGET_DIR'"
        echo "Image set '$SET_NAME' is ready for processing"
        ;;
        
    create-set)
        if [[ -z "$SET_NAME" ]]; then
            echo "Error: No set name provided"
            show_help
            exit 1
        fi
        
        # Create the target directory
        TARGET_DIR="$IMAGE_SETS_DIR/$SET_NAME"
        mkdir -p "$TARGET_DIR"
        
        echo "Created new image set directory: $TARGET_DIR"
        echo "You can now copy or move your images into this directory"
        ;;
        
    list)
        echo "Available image sets:"
        echo "-----------------"
        
        found=0
        for dir in "$IMAGE_SETS_DIR"/*; do
            if [[ -d "$dir" ]]; then
                found=1
                set_name=$(basename "$dir")
                img_count=$(find "$dir" -maxdepth 1 -type f \( -name "*.jpg" -o -name "*.png" \) | wc -l)
                echo "- $set_name ($img_count images)"
            fi
        done
        
        if [[ $found -eq 0 ]]; then
            echo "No image sets found. Use 'create-set' to create one."
        fi
        ;;
        
    *)
        echo "Error: No command specified"
        show_help
        exit 1
        ;;
esac 
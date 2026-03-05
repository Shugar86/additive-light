# Collaboration Guidelines for R&D Work

## Overview
This document outlines the best practices for collaborative Research and Development (R&D) projects in our repository. Following these guidelines will help to streamline our workflow and improve the quality of our contributions.

## Branching Strategy
1. **Main Branch**: Our primary branch (`main`) should always contain stable and tested code. All development work occurs on separate branches.
2. **Feature Branches**: When starting work on a new feature, create a new branch off the `main` branch. The naming convention is `feature/<description>`.
   - Example: `feature/add-new-functionality`
3. **Bugfix Branches**: For any bug fixes, create branches using the convention `bugfix/<description>`.
   - Example: `bugfix/fix-crash-on-launch`

## Workflow
1. **Create a Branch**: Before starting your work, ensure you create a new branch as outlined above.
2. **Regular Commits**: Commit changes regularly with clear, descriptive messages that explain what changes were made and why.
   - Example: `git commit -m "Add feature X to improve performance"`
3. **Pull Requests**: After completing a feature or fix, push your changes to the remote repository and create a pull request (PR) from your branch to the `main` branch.
   - Ensure that your PR description includes what has been changed, the motivation behind the changes, and any related issues.

## PR Process
1. **Draft PR**: Begin with a draft PR to initiate the discussion about your changes even if it is not finalized.
2. **Reviewers**: Assign necessary reviewers based on the nature of the changes. A minimum of two reviews is required before merging.
3. **Continuous Integration**: Ensure all automated tests pass before your PR can be merged. If any tests fail, address the issues first.
4. **Merge**: Once approved and all checks are passed, merge your PR into the `main` branch. Use the 'Squash and Merge' option to keep history concise.

## Conclusion
Following these guidelines will ensure a smooth collaborative experience and maintain the quality of our project. Happy coding!
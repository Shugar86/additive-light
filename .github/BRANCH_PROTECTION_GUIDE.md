# Branch Protection Guide

## Purpose
This guide explains how to set up branch protection rules for the `develop` and `main` branches in your GitHub repository.

## Setting Up Branch Protection Rules
1. **Navigate to Your Repository**  
   Go to your repository on GitHub.

2. **Access Settings**  
   Click on the `Settings` tab located at the top of your repository page.

3. **Select Branches**  
   In the left sidebar, click on `Branches`.

4. **Add Branch Protection Rule**  
   - Under the `Branch protection rules` section, click on `Add rule`.

5. **Specify Branch Name Pattern**  
   - For the `develop` branch, enter `develop`.  
   - For the `main` branch, enter `main`.  
   You can also use wildcard patterns (e.g., `release/*`).

6. **Configure Protection Settings**  
   Choose the settings you want to enforce for the branch protection rule:
   - **Require pull request reviews before merging**  
     (recommended: at least one approval)
   - **Require status checks to pass before merging**  
     (specify which checks must pass)
   - **Include administrators**  
     (to enforce these rules even for repository admins)

7. **Create Rule**  
   Click `Create` or `Save changes` to apply the branch protection rule.

8. **Repeat for Additional Branches**  
   If needed, repeat these steps for other branches (e.g., `develop` if you started with `main`).

## Conclusion  
Branch protection rules help maintain the integrity of your code in important branches. Make sure to review these settings periodically to fit your workflow and team needs.
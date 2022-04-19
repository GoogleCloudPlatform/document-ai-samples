# How to become a contributor and submit your own code

New components are always welcome!

If you're interested in contributing a new component or making a changes to the existing application,
please open an issue for discussion first.

## Contributing A New Component

1. Submit an issue describing your proposed change to this repository.
2. A repository owner will respond to your issue promptly. If you don't see a response within
   a few days, please ping the owner assigned to your issue.
3. If your proposed change is accepted, and you haven't already done so, sign a
   Contributor License Agreement (see details above).
4. Fork this repository, develop and test your code changes. Tests are required for all
   components.
5. Ensure that your code adheres to the existing style.
6. Ensure that your code has an appropriate set of unit tests which all pass.
7. Submit a pull request.

### Adding a New Component

To add a component to the existing application make sure you're in the component directory.

```bash
cd Frontend/src/app/components
```

Then run

```bash

ng generate component <name> [options]

```

[For more information about generating components][https://angular.io/cli/generate#component-command]

This will create a folder with all the files you need for the component. To add this component to the main application all you need to do is copy the component selector and add it to the base-layer component.

```html
<app-component-selector></app-component-selector>
```

After adding the component make sure to run lint on the new component:

To run lint on the Frontend make sure you're in the Frontend directory and run

```bash
ng lint --fix
```

To run lint on the Backend make sure you're in the demo directory and run

```bash
pylint Backend
```

## Running Tests

### Backend Tests

To run all backend tests make sure you're in the API directory and run

```bash
python helper_test.py
```

### Frontend Test

To run all frontend tests

```bash
ng test
```

To run all tests and get code coverage

```bash
ng test --no-watch --code-coverage
```

## Contributor License Agreements

Before we can take contributions, we have to jump a couple of legal hurdles.

Please fill out either the individual or corporate Contributor License
Agreement (CLA).

- If you are an individual writing original source code and you're sure you
  own the intellectual property, then you'll need to sign an [individual CLA](https://developers.google.com/open-source/cla/individual).
- If you work for a company that wants to allow you to contribute your work,
  then you'll need to sign a [corporate CLA](https://developers.google.com/open-source/cla/corporate).

Follow either of the two links above to access the appropriate CLA and
instructions for how to sign and return it. Once we receive it, we'll
be able to accept your pull requests.

## Code Reviews

After meeting the above criteria, your code will need to be approved by a reviewer before it can be merged into main.
If you do not hear from your repository owner reviewer within a day (and you know they are not OOO),
send them a friendly ping so that you can better understand the review cadence for your PR.
All the repository owners are juggling reviews alongside other work, and their velocities can vary, but they are happy to hear from you.
